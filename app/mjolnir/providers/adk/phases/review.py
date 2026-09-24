# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from typing import Union

from google.adk import Context
from google.adk.workflow import node

from constants import (
    MAX_REVIEW_POC_PROMPT_CHARS,
    PHASE_FINAL_REVIEW_ID,
    PHASE_FINAL_REVIEW_NAME,
    PHASE_INITIAL_REVIEW_ID,
    PHASE_INITIAL_REVIEW_NAME,
    REVIEW_TASK_PROMPT_TEMPLATE,
    REVIEW_WITH_POC_TASK_PROMPT_TEMPLATE,
)
from data.review_finding import ReviewFinding
from data.status import Status
from data.vulnerability import Vulnerability
from providers.adk.agents.reviewer import (
    build_reviewer_instruction,
    get_reviewer_agent,
    get_reviewer_tools,
)
from providers.adk.phases.audit import checkpoint_audit_findings
from providers.adk.utilities.async_runner import (
    run_agent_node,
    run_batch_with_concurrency,
)
from providers.adk.utilities.cache_manager import PhaseContextCache
from utilities.logger import logger


async def _run_review_pass(
    ctx: Context,
    node_input: list[Vulnerability] | None = None,
    *,
    phase_id: str = PHASE_INITIAL_REVIEW_ID,
    phase_name: str = PHASE_INITIAL_REVIEW_NAME,
    evaluate_poc: bool = False,
) -> list[Vulnerability]:
    """Shared adversarial review engine for both Initial Review (pre-PoC) and Final Review (with PoC)."""
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
    run_dir = ctx.state.get("run_dir")

    reviewer_tools = get_reviewer_tools(enable_project_expert=enable_project_expert)
    reviewer_instruction = build_reviewer_instruction(
        threat_model,
        project_summary,
        evaluate_poc=evaluate_poc,
        tools=reviewer_tools,
    )

    with PhaseContextCache(
        model=model,
        instruction=reviewer_instruction,
        tools=reviewer_tools,
        output_schema=ReviewFinding,
        display_name=f"mjolnir-{phase_id}-{Path(code_dir).name}",
    ) as cache:
        reviewer_agent = get_reviewer_agent(
            model,
            threat_model,
            project_summary,
            cached_content=cache.cache_name,
            evaluate_poc=evaluate_poc,
            enable_project_expert=enable_project_expert,
        )

        async def review_single_vuln(vuln: Union[Vulnerability, dict]) -> Vulnerability:
            if isinstance(vuln, dict):
                vuln = Vulnerability.model_validate(vuln)

            if getattr(vuln, "status", Status.OPEN) != Status.OPEN:
                vuln.add_skipped(phase_id, phase_name, f"Skipped: Status is {vuln.status}")
                return vuln

            exclude_fields = set() if evaluate_poc else {"poc"}
            finding_payload = vuln.model_dump_json(indent=2, exclude=exclude_fields)
            if evaluate_poc and vuln.poc:
                poc_content = vuln.poc
                if len(poc_content) > MAX_REVIEW_POC_PROMPT_CHARS:
                    half = MAX_REVIEW_POC_PROMPT_CHARS // 2
                    poc_content = (
                        poc_content[:half]
                        + "\n... [PoC excerpt truncated for review context window limit] ...\n"
                        + poc_content[-half:]
                    )
                review_prompt = REVIEW_WITH_POC_TASK_PROMPT_TEMPLATE.format(
                    finding_payload=finding_payload, poc=poc_content
                )
            else:
                review_prompt = REVIEW_TASK_PROMPT_TEMPLATE.format(finding_payload=finding_payload)

            try:
                verdict = await run_agent_node(
                    ctx,
                    reviewer_agent,
                    node_input=review_prompt,
                    expected_schema=ReviewFinding,
                    run_id=f"{phase_id}_{vuln.id}",
                )

                if verdict:
                    if getattr(verdict, "refusal_reason", None):
                        vuln.add_skipped(
                            phase_id,
                            phase_name,
                            f"Model soft refusal: {verdict.refusal_reason}",
                        )
                    else:
                        vuln.add(
                            phase_id=phase_id,
                            phase_name=phase_name,
                            finding=verdict,
                        )
                else:
                    vuln.add_skipped(
                        phase_id,
                        phase_name,
                        "Reviewer agent returned empty/unparseable verdict after retries.",
                    )
            except Exception as rev_err:
                logger.error(f" [Reviewer FATAL] Failed {vuln.file} after max retries: {rev_err}")
                vuln.add_skipped(
                    phase_id,
                    phase_name,
                    f"FATAL ERROR: AI Reviewer agent failed after retries ({type(rev_err).__name__}).",
                )

            return vuln

        results, exceptions = await run_batch_with_concurrency(
            items=vulnerabilities,
            worker_fn=review_single_vuln,
            concurrency_limit=batch_size,
            desc=f"{phase_name}",
            unit="finding",
            usage_tracker=ctx.state.get("usage_tracker"),
        )

    if exceptions:
        logger.warning(f"{phase_name} encountered {len(exceptions)} fatal errors.")
        for exc in exceptions:
            logger.error(f"{phase_name} error: {exc}", exc_info=exc)

    run_dir = ctx.state.get("run_dir")
    ctx.state["vulnerabilities"] = results

    await checkpoint_audit_findings(results, run_dir, phase_id=phase_id, state=ctx.state)

    logger.info(f"{phase_name} complete.")
    return results


@node(rerun_on_resume=True)
async def initial_review_phase(
    ctx: Context, node_input: list[Vulnerability] | None = None
) -> list[Vulnerability]:
    """Initial Adversarial Review Phase (evaluates static code reachability & threat model without PoC)."""
    return await _run_review_pass(
        ctx,
        node_input,
        phase_id=PHASE_INITIAL_REVIEW_ID,
        phase_name=PHASE_INITIAL_REVIEW_NAME,
        evaluate_poc=False,
    )


@node(rerun_on_resume=True)
async def final_review_phase(
    ctx: Context, node_input: list[Vulnerability] | None = None
) -> list[Vulnerability]:
    """Final Adversarial Review Phase (evaluates finding alongside generated Proof-of-Concept)."""
    return await _run_review_pass(
        ctx,
        node_input,
        phase_id=PHASE_FINAL_REVIEW_ID,
        phase_name=PHASE_FINAL_REVIEW_NAME,
        evaluate_poc=True,
    )


# Backward-compatible alias
review_phase = initial_review_phase
