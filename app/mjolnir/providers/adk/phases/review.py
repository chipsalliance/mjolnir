# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import hashlib
from typing import Union
from google.adk import Context
from google.adk.workflow import node
from utilities.logger import logger
from data.status import Status
from data.review_finding import ReviewFinding
from data.vulnerability import Vulnerability
from providers.adk.utilities.async_runner import (
    run_agent_with_backoff,
    run_batch_with_concurrency,
)
from providers.adk.agents.reviewer import get_reviewer_agent


@node(rerun_on_resume=True)
async def review_phase(
    ctx: Context, node_input: list[Vulnerability]
) -> list[Vulnerability]:
    """Phase 2: Adversarial Triaging (Validation)."""
    logger.write("Starting Phase 2: Adversarial Reviews...", stdout=True)

    vulnerabilities = node_input
    if not vulnerabilities:
        logger.write("No vulnerabilities to review.", stdout=True)
        return []

    model = ctx.state["model"]
    threat_model = ctx.state["threat_model_context"]
    batch_size = ctx.state["batch_size"]
    reviewer_agent = get_reviewer_agent(model, threat_model)

    async def review_single_vuln(vuln: Union[Vulnerability, dict]) -> Vulnerability:
        if isinstance(vuln, dict):
            vuln = Vulnerability.model_validate(vuln)

        if getattr(vuln, "status", Status.OPEN) != Status.OPEN:
            vuln.add_skipped("2", "Initial Review", f"Skipped: Status is {vuln.status}")
            return vuln

        run_id = f"review_{vuln.id}"

        try:
            verdict = await run_agent_with_backoff(
                ctx,
                reviewer_agent,
                node_input=f"Audit Finding:\n{vuln.model_dump_json(indent=2)}",
                expected_schema=ReviewFinding,
                run_id=f"{run_id}_rev",
            )
            if verdict:
                vuln.add(phase_id="2", phase_name="Initial Review", finding=verdict)
            else:
                vuln.add_skipped(
                    "2",
                    "Initial Review",
                    "Reviewer agent returned empty/unparseable verdict after retries.",
                )
        except Exception as rev_err:
            logger.write(
                f" [Reviewer FATAL] Failed {vuln.file} after max retries: {rev_err}",
                stdout=True,
            )
            vuln.add_skipped(
                "2",
                "Initial Review",
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
        logger.write(
            f"WARNING: Phase 2 encountered {len(exceptions)} fatal errors.",
            stdout=True,
        )
        for exc in exceptions:
            logger.error(f"Phase 2 error: {exc}", exc_info=exc)

    logger.write("Phase 2 complete.", stdout=True)
    return results
