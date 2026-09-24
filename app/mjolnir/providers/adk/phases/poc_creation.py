# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import shutil
import subprocess
from pathlib import Path
from typing import Union

from google.adk import Context
from google.adk.workflow import node

from constants import (
    MAX_POC_DIFF_EXCERPT_CHARS,
    MAX_POC_OUTPUT_EXCERPT_CHARS,
    PHASE_POC_CREATION_ID,
    PHASE_POC_CREATION_NAME,
    POC_CREATION_TASK_PROMPT_TEMPLATE,
    POC_DIFF_TRUNCATION_MARKER,
    POC_EXECUTION_EMPTY_SECTION,
    POC_EXECUTION_PRESENT_SECTION_TEMPLATE,
    POC_OUTPUT_TRUNCATION_MARKER,
    POC_PATCH_EMPTY_SECTION,
    POC_PATCH_PRESENT_SECTION_TEMPLATE,
    POC_SYNTHESIZED_OVERVIEW_SECTION_TEMPLATE,
    POC_VERIFICATION_STATUS_SECTION_TEMPLATE,
    POC_WORKTREES_SUBDIR,
)
from data.exploit_finding import ExploitFinding
from data.status import Status
from data.vulnerability import Vulnerability
from providers.adk.agents.exploiter import (
    build_exploiter_instruction,
    get_exploiter_agent,
    get_exploiter_tools,
)
from providers.adk.phases.audit import checkpoint_audit_findings
from providers.adk.utilities.async_runner import (
    run_agent_node,
    run_batch_with_concurrency,
)
from providers.adk.utilities.cache_manager import PhaseContextCache
from utilities.logger import logger
from utilities.worktree_sandbox import WorktreeSandbox


def _assemble_ground_truth_poc_bundle(
    finding: ExploitFinding,
    sandbox: WorktreeSandbox,
) -> str:
    """Combines the agent's PoC explanation with the ground-truth sandbox diff and test execution output."""
    actual_diff = sandbox.get_diff().strip()
    removed_baseline_lines = sandbox.count_removed_baseline_lines()
    prod_modified = sandbox.has_production_code_modifications()

    # Mechanical verification gate:
    # A PoC is verified ONLY IF:
    # 1. Non-empty diff exists.
    # 2. At least one harness command was executed.
    # 3. No baseline lines were deleted or modified.
    # 4. No production code files were altered (only test/harness code).
    # 5. Last test command reproduced the vulnerability (non-zero exit code).
    has_test_execution = bool(sandbox.command_history)
    last_cmd_reproduced = (
        sandbox.command_history[-1].returncode != 0 if has_test_execution else False
    )

    if finding.poc_verified:
        if (
            not actual_diff
            or not has_test_execution
            or removed_baseline_lines > 0
            or prod_modified
            or not last_cmd_reproduced
        ):
            finding.poc_verified = False

    status_lines = [
        f"- **Baseline Lines Modified/Deleted**: `{removed_baseline_lines}`",
        f"- **Production Code Modified**: `{prod_modified}`",
    ]
    if has_test_execution:
        status_lines.append(
            f"- **Final Command Exit Code**: `{sandbox.command_history[-1].returncode}`"
        )

    sections: list[str] = [
        POC_VERIFICATION_STATUS_SECTION_TEMPLATE.format(
            poc_verified=finding.poc_verified,
            patch_present=bool(actual_diff),
            commands_executed=len(sandbox.command_history),
        )
        + "\n"
        + "\n".join(status_lines)
    ]

    if finding.poc and finding.poc.strip():
        sections.append(POC_SYNTHESIZED_OVERVIEW_SECTION_TEMPLATE.format(poc=finding.poc.strip()))

    if actual_diff:
        diff_excerpt = actual_diff
        if len(diff_excerpt) > MAX_POC_DIFF_EXCERPT_CHARS:
            half = MAX_POC_DIFF_EXCERPT_CHARS // 2
            diff_excerpt = diff_excerpt[:half] + POC_DIFF_TRUNCATION_MARKER + diff_excerpt[-half:]
        sections.append(POC_PATCH_PRESENT_SECTION_TEMPLATE.format(actual_diff=diff_excerpt))
    else:
        sections.append(POC_PATCH_EMPTY_SECTION)

    if sandbox.command_history:
        last_rec = sandbox.command_history[-1]
        out_excerpt = last_rec.output
        # Preserve both the first half (compiler/test banner) and last half (panic/assertion traceback)
        if len(out_excerpt) > MAX_POC_OUTPUT_EXCERPT_CHARS:
            half = MAX_POC_OUTPUT_EXCERPT_CHARS // 2
            out_excerpt = out_excerpt[:half] + POC_OUTPUT_TRUNCATION_MARKER + out_excerpt[-half:]
        sections.append(
            POC_EXECUTION_PRESENT_SECTION_TEMPLATE.format(
                command=last_rec.command,
                returncode=last_rec.returncode,
                output=out_excerpt,
            )
        )
    else:
        sections.append(POC_EXECUTION_EMPTY_SECTION)

    return "\n\n".join(sections)


@node(rerun_on_resume=True)
async def poc_creation_phase(
    ctx: Context, node_input: list[Vulnerability] | None = None
) -> list[Vulnerability]:
    """Proof-of-Concept Creation Phase (synthesizes and executes unit-test PoCs in isolated sandboxes)."""
    phase_id = PHASE_POC_CREATION_ID
    phase_name = PHASE_POC_CREATION_NAME
    logger.info(f"Starting {phase_name} ({phase_id})...")

    vulnerabilities = (
        node_input if isinstance(node_input, list) else list(ctx.state.get("vulnerabilities", []))
    )
    if not vulnerabilities:
        logger.info(f"No vulnerabilities for {phase_name}.")
        ctx.state["vulnerabilities"] = []
        return []

    model = ctx.state["model"]
    threat_model = ctx.state["threat_model_context"]
    project_summary = ctx.state.get("project_expert_summary", "")
    enable_project_expert = ctx.state["enable_project_expert"]
    batch_size = ctx.state["batch_size"]
    code_dir = ctx.state.get("code_dir", "target")
    run_dir = ctx.state.get("run_dir") or "."

    exploiter_tools = get_exploiter_tools(enable_project_expert=enable_project_expert)
    exploiter_instruction = build_exploiter_instruction(
        threat_model,
        project_summary,
        tools=exploiter_tools,
    )

    with PhaseContextCache(
        model=model,
        instruction=exploiter_instruction,
        tools=exploiter_tools,
        output_schema=ExploitFinding,
        display_name=f"mjolnir-{phase_id}-{Path(code_dir).name}",
    ) as cache:
        exploiter_agent = get_exploiter_agent(
            model,
            threat_model,
            project_summary,
            cached_content=cache.cache_name,
            enable_project_expert=enable_project_expert,
        )

        async def create_poc_for_vuln(vuln: Union[Vulnerability, dict]) -> Vulnerability:
            if isinstance(vuln, dict):
                vuln = Vulnerability.model_validate(vuln)

            if getattr(vuln, "status", Status.OPEN) != Status.OPEN:
                vuln.add_skipped(phase_id, phase_name, f"Skipped: Status is {vuln.status}")
                return vuln

            finding_payload = vuln.model_dump_json(indent=2, exclude={"poc"})
            poc_prompt = POC_CREATION_TASK_PROMPT_TEMPLATE.format(finding_payload=finding_payload)

            try:
                async with WorktreeSandbox(
                    source_code_dir=Path(code_dir),
                    workspace_dir=Path(run_dir),
                    vuln_id=vuln.id,
                ) as sandbox:
                    exploit_res = await run_agent_node(
                        ctx,
                        exploiter_agent,
                        node_input=poc_prompt,
                        expected_schema=ExploitFinding,
                        run_id=f"{phase_id}_{vuln.id}",
                    )

                    if exploit_res:
                        if getattr(exploit_res, "refusal_reason", None):
                            vuln.add_skipped(
                                phase_id,
                                phase_name,
                                f"Model soft refusal: {exploit_res.refusal_reason}",
                            )
                        else:
                            if not exploit_res.test_command and sandbox.command_history:
                                exploit_res.test_command = sandbox.command_history[-1].command
                            exploit_res.poc = _assemble_ground_truth_poc_bundle(
                                exploit_res, sandbox
                            )
                            vuln.add(
                                phase_id=phase_id,
                                phase_name=phase_name,
                                finding=exploit_res,
                            )
                    else:
                        vuln.add_skipped(
                            phase_id,
                            phase_name,
                            "ExploitCreationAgent returned empty/unparseable result after retries.",
                        )
            except Exception as poc_err:
                logger.error(f" [Exploiter FATAL] Failed {vuln.file} after max retries: {poc_err}")
                vuln.add_skipped(
                    phase_id,
                    phase_name,
                    f"FATAL ERROR: ExploitCreationAgent failed ({type(poc_err).__name__}).",
                )

            return vuln

        # Execute PoC synthesis sequentially (concurrency_limit=1) to prevent build lock contention
        # and maximize build cache hit rates across findings in the shared scratch worktree.
        results, exceptions = await run_batch_with_concurrency(
            items=vulnerabilities,
            worker_fn=create_poc_for_vuln,
            concurrency_limit=1,
            desc=f"{phase_name}",
            unit="finding",
            usage_tracker=ctx.state.get("usage_tracker"),
        )

    if exceptions:
        logger.warning(f"{phase_name} encountered {len(exceptions)} fatal errors.")
        for exc in exceptions:
            logger.error(f"{phase_name} error: {exc}", exc_info=exc)

    scratch_dir = Path(run_dir) / POC_WORKTREES_SUBDIR / "scratch"
    if scratch_dir.exists():
        subprocess.run(
            ["git", "-C", str(Path(code_dir)), "worktree", "remove", "--force", str(scratch_dir)],
            capture_output=True,
            check=False,
        )
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir, ignore_errors=True)

    ctx.state["vulnerabilities"] = results
    await checkpoint_audit_findings(results, run_dir, phase_id=phase_id, state=ctx.state)

    logger.info(f"{phase_name} complete.")
    return results
