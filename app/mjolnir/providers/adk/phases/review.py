# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from typing import Union

from google.adk import Context
from google.adk.workflow import node

from constants import PHASE_2_ID, PHASE_2_NAME
from data.review_finding import ReviewFinding
from data.status import Status
from data.vulnerability import Vulnerability
from providers.adk.agents.reviewer import (
    REVIEWER_TOOLS,
    build_reviewer_instruction,
    get_reviewer_agent,
)
from providers.adk.phases.audit import checkpoint_audit_findings
from providers.adk.utilities.async_runner import (
    run_agent_node,
    run_batch_with_concurrency,
)
from providers.adk.utilities.cache_manager import PhaseContextCache
from utilities.logger import logger


@node(rerun_on_resume=True)
async def review_phase(ctx: Context, node_input: list[Vulnerability]) -> list[Vulnerability]:
    """Phase 2: Adversarial Triaging (Validation)."""
    logger.info("Starting Phase 2: Adversarial Reviews...")

    vulnerabilities = node_input
    if not vulnerabilities:
        logger.info("No vulnerabilities to review.")
        return []

    model = ctx.state["model"]
    threat_model = ctx.state["threat_model_context"]
    project_summary = ctx.state.get("project_expert_summary", "")
    batch_size = ctx.state["batch_size"]
    code_dir = ctx.state.get("code_dir", "target")

    reviewer_instruction = build_reviewer_instruction(threat_model, project_summary)

    with PhaseContextCache(
        model=model,
        instruction=reviewer_instruction,
        tools=REVIEWER_TOOLS,
        output_schema=ReviewFinding,
        display_name=f"mjolnir-phase2-{Path(code_dir).name}",
    ) as cache:
        reviewer_agent = get_reviewer_agent(
            model, threat_model, project_summary, cached_content=cache.cache_name
        )

        async def review_single_vuln(vuln: Union[Vulnerability, dict]) -> Vulnerability:
            if isinstance(vuln, dict):
                vuln = Vulnerability.model_validate(vuln)

            if getattr(vuln, "status", Status.OPEN) != Status.OPEN:
                vuln.add_skipped(PHASE_2_ID, PHASE_2_NAME, f"Skipped: Status is {vuln.status}")
                return vuln

            try:
                verdict = await run_agent_node(
                    ctx,
                    reviewer_agent,
                    node_input=f"Audit Finding:\n{vuln.model_dump_json(indent=2)}",
                    expected_schema=ReviewFinding,
                    run_id=str(vuln.id),
                )

                if verdict:
                    if getattr(verdict, "refusal_reason", None):
                        vuln.add_skipped(
                            PHASE_2_ID,
                            PHASE_2_NAME,
                            f"Model soft refusal: {verdict.refusal_reason}",
                        )
                    else:
                        vuln.add(phase_id=PHASE_2_ID, phase_name=PHASE_2_NAME, finding=verdict)
                else:
                    vuln.add_skipped(
                        PHASE_2_ID,
                        PHASE_2_NAME,
                        "Reviewer agent returned empty/unparseable verdict after retries.",
                    )
            except Exception as rev_err:
                logger.error(f" [Reviewer FATAL] Failed {vuln.file} after max retries: {rev_err}")
                vuln.add_skipped(
                    PHASE_2_ID,
                    PHASE_2_NAME,
                    f"FATAL ERROR: AI Reviewer agent failed after retries ({type(rev_err).__name__}).",
                )

            return vuln

        results, exceptions = await run_batch_with_concurrency(
            items=vulnerabilities,
            worker_fn=review_single_vuln,
            concurrency_limit=batch_size,
            desc="Reviewing findings",
            unit="finding",
            usage_tracker=ctx.state.get("usage_tracker"),
        )

    if exceptions:
        logger.warning(f"Phase 2 encountered {len(exceptions)} fatal errors.")
        for exc in exceptions:
            logger.error(f"Phase 2 error: {exc}", exc_info=exc)

    run_dir = ctx.state.get("run_dir")

    await checkpoint_audit_findings(results, run_dir, phase_id=PHASE_2_ID)

    logger.info("Phase 2 complete.")
    return results
