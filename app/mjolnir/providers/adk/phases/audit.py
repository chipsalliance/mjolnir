# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import asyncio
import json
from pathlib import Path

from google.adk import Context
from google.adk.workflow import node

from constants import (
    AUDIT_FILE_TASK_PROMPT_TEMPLATE,
    AUDIT_PR_DIFF_SECTION_TEMPLATE,
    AUDIT_PR_DIFF_TASK_PROMPT_TEMPLATE,
    PHASE_DISCOVERY_ID,
    PHASE_DISCOVERY_NAME,
)
from data.security_report import SecurityReport
from data.vulnerability import Vulnerability
from providers.adk.agents.auditor import (
    build_auditor_instruction,
    get_auditor_agent,
    get_auditor_tools,
)
from providers.adk.utilities.async_runner import (
    run_agent_node,
    run_batch_with_concurrency,
)
from providers.adk.utilities.cache_manager import PhaseContextCache
from utilities.git import get_file_diff_async
from utilities.logger import logger


def _write_checkpoint_sync(audit_path: Path, vulns_data: list[dict]) -> None:
    with open(audit_path, "w") as f:
        json.dump(vulns_data, f, indent=2)


async def _read_file_contents_async(full_file_path: Path) -> str:
    return await asyncio.to_thread(full_file_path.read_text, encoding="utf-8", errors="ignore")


async def checkpoint_audit_findings(
    vulns: list[Vulnerability],
    run_dir: str,
    phase_id: str = PHASE_DISCOVERY_ID,
    filename: str = None,
    state: dict | None = None,
) -> Path | None:
    """Checkpoints vulnerabilities to a JSON file on disk without blocking the event loop."""
    if not run_dir or not Path(run_dir).exists():
        return None
    checkpoint_name = filename or f"finding_phase_{phase_id}.json"
    audit_path = Path(run_dir) / checkpoint_name
    try:
        vulns_data = [v.model_dump() for v in vulns]
        await asyncio.to_thread(_write_checkpoint_sync, audit_path, vulns_data)
        if state is not None:
            state["last_checkpoint_path"] = str(audit_path)
        logger.info(f"Checkpointed {len(vulns)} [{phase_id}] vulnerabilities to {audit_path}")
        return audit_path
    except Exception as e:
        logger.error(f"Failed to checkpoint [{phase_id}] vulnerabilities: {e}")
        return None


@node(rerun_on_resume=True)
async def discovery_phase(ctx: Context, node_input: list[str] | None = None) -> list[Vulnerability]:
    """Dynamic File Auditing (Discovery) Phase."""
    logger.info(f"Starting {PHASE_DISCOVERY_NAME} ({PHASE_DISCOVERY_ID})...")

    target_files = node_input if isinstance(node_input, list) else list(ctx.state.get("files", []))
    model = ctx.state["model"]
    code_dir = ctx.state["code_dir"]
    threat_model = ctx.state["threat_model_context"]
    project_summary = ctx.state.get("project_expert_summary", "")
    enable_project_expert = ctx.state["enable_project_expert"]
    batch_size = ctx.state["batch_size"]
    run_dir = ctx.state.get("run_dir")

    auditor_tools = get_auditor_tools(enable_project_expert=enable_project_expert)
    auditor_instruction = build_auditor_instruction(
        threat_model, project_summary, tools=auditor_tools
    )

    with PhaseContextCache(
        model=model,
        instruction=auditor_instruction,
        tools=auditor_tools,
        output_schema=SecurityReport,
        display_name=f"mjolnir-{PHASE_DISCOVERY_ID}-{Path(code_dir).name}",
    ) as cache:
        auditor_agent = get_auditor_agent(
            model,
            threat_model,
            project_summary,
            cached_content=cache.cache_name,
            enable_project_expert=enable_project_expert,
        )

        diff_base = ctx.state.get("diff_base")
        diff_head = ctx.state.get("diff_head")

        async def audit_single_file(f_path: str) -> list[Vulnerability]:
            full_file_path = Path(code_dir) / f_path
            try:
                contents = await _read_file_contents_async(full_file_path)
            except Exception as e:
                logger.error(f"Could not read {f_path}: {e}")
                return []

            if diff_base:
                file_diff = await get_file_diff_async(
                    code_dir, diff_base, diff_head or "HEAD", f_path
                )
                diff_section = (
                    AUDIT_PR_DIFF_SECTION_TEMPLATE.format(file_diff=file_diff) if file_diff else ""
                )
                file_input = AUDIT_PR_DIFF_TASK_PROMPT_TEMPLATE.format(
                    f_path=f_path, diff_section=diff_section, contents=contents
                )
            else:
                file_input = AUDIT_FILE_TASK_PROMPT_TEMPLATE.format(
                    f_path=f_path, contents=contents
                )

            report = await run_agent_node(
                ctx,
                auditor_agent,
                node_input=file_input,
                expected_schema=SecurityReport,
                run_id=f_path,
            )

            if report is None:
                logger.warning(
                    f"AuditorAgent returned no report for '{f_path}' "
                    "(potential refusal, timeout, or schema validation failure)."
                )
                return []

            if not hasattr(report, "vulnerabilities") or not report.vulnerabilities:
                return []

            vulns: list[Vulnerability] = []
            for af in report.vulnerabilities:
                af.file = f_path
                vulns.append(
                    Vulnerability.from_audit_finding(
                        af,
                        file_path=f_path,
                        phase_id=PHASE_DISCOVERY_ID,
                        phase_name=PHASE_DISCOVERY_NAME,
                    )
                )
            return vulns

        results, exceptions = await run_batch_with_concurrency(
            items=target_files,
            worker_fn=audit_single_file,
            concurrency_limit=batch_size,
            desc="Scanning files",
            unit="file",
            usage_tracker=ctx.state.get("usage_tracker"),
        )

    if exceptions:
        logger.warning(f"{PHASE_DISCOVERY_NAME} encountered {len(exceptions)} fatal errors.")
        for exc in exceptions:
            logger.error(f"{PHASE_DISCOVERY_NAME} error: {exc}", exc_info=exc)

    flat_vulns = [vuln for file_vulns in results for vuln in file_vulns]
    ctx.state["vulnerabilities"] = flat_vulns
    await checkpoint_audit_findings(
        flat_vulns, run_dir, phase_id=PHASE_DISCOVERY_ID, state=ctx.state
    )

    logger.info(f"{PHASE_DISCOVERY_NAME} complete. Found {len(flat_vulns)} total vulnerabilities.")

    return flat_vulns


audit_phase = discovery_phase
