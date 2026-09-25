# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Lightweight upfront deduplication phase executed directly after discovery."""

import json
from typing import Any, Union

from google.adk import Context
from google.adk.workflow import node

from constants import (
    DEDUPLICATION_TASK_PROMPT_TEMPLATE,
    PHASE_DEDUPLICATION_ID,
    PHASE_DEDUPLICATION_NAME,
)
from data.deduplication_finding import (
    DeduplicationFinding,
    DeduplicationReport,
)
from data.status import Status
from data.vulnerability import Vulnerability
from providers.adk.agents.deduplicator import get_deduplicator_agent
from providers.adk.phases.audit import checkpoint_audit_findings
from providers.adk.utilities.async_runner import run_agent_node
from utilities.bucket_loader import load_historical_open_vulnerabilities
from utilities.logger import logger


def _serialize_candidate_vuln(vuln: Vulnerability) -> dict[str, Any]:
    """Serializes a candidate Vulnerability into a concise dict for the agent."""
    return {
        "id": vuln.id,
        "file": vuln.file,
        "location": vuln.location,
        "title": vuln.title,
        "severity": vuln.severity.value if hasattr(vuln.severity, "value") else str(vuln.severity),
        "description": vuln.description,
        "recommendation": vuln.recommendation,
    }


def _apply_dedup_report(
    vulns: list[Vulnerability],
    report: DeduplicationReport | None,
    phase_id: str,
    phase_name: str,
) -> None:
    """Applies deduplication decisions directly to findings, updating status and duplicate_of."""
    if not report or not report.decisions:
        for v in vulns:
            v.add_skipped(phase_id, phase_name, "No deduplication decision returned.")
        return

    decision_map = {d.finding_id: d for d in report.decisions}
    dup_count = 0

    for v in vulns:
        dec = decision_map.get(v.id)
        if dec and dec.status == Status.DUPLICATE and dec.duplicate_of:
            v.add(
                phase_id=phase_id,
                phase_name=phase_name,
                finding=DeduplicationFinding(
                    status=Status.DUPLICATE,
                    duplicate_of=dec.duplicate_of,
                    justification=dec.justification,
                ),
            )
            dup_count += 1
        else:
            v.add(
                phase_id=phase_id,
                phase_name=phase_name,
                finding=DeduplicationFinding(
                    status=Status.OPEN,
                    duplicate_of=None,
                    justification=dec.justification if dec else "Kept as unique Open finding.",
                ),
            )

    logger.info(
        f"[{phase_id}] Upfront Deduplication: {dup_count} marked Duplicate (will bypass review/PoC); "
        f"{len(vulns) - dup_count} unique Open finding(s) proceed downstream."
    )


@node(rerun_on_resume=True)
async def deduplication_phase(ctx: Context, node_input: Any = None) -> list[Vulnerability]:
    """Upfront Deduplication Phase: collapses intra-run and historical duplicates immediately after discovery."""
    phase_id = PHASE_DEDUPLICATION_ID
    phase_name = PHASE_DEDUPLICATION_NAME
    logger.info(f"Starting {phase_name} ({phase_id})...")

    raw_vulns = (
        node_input if isinstance(node_input, list) else list(ctx.state.get("vulnerabilities", []))
    )
    if not raw_vulns:
        logger.info(f"No vulnerabilities for {phase_name}.")
        ctx.state["vulnerabilities"] = []
        return []

    vulnerabilities = [
        Vulnerability.model_validate(v) if isinstance(v, dict) else v for v in raw_vulns
    ]

    open_vulns = [v for v in vulnerabilities if getattr(v, "status", Status.OPEN) == Status.OPEN]
    if not open_vulns:
        ctx.state["vulnerabilities"] = vulnerabilities
        return vulnerabilities

    run_dir = ctx.state.get("run_dir")
    historical_open = await load_historical_open_vulnerabilities(
        bucket=ctx.state.get("bucket"),
        project_name=ctx.state.get("project_name"),
        project_output_dir=ctx.state.get("project_output_dir"),
        current_run_dir=run_dir,
    )

    # Fast path: only 1 finding and no history -> trivially unique without LLM call
    if len(open_vulns) == 1 and not historical_open:
        open_vulns[0].add(
            phase_id=phase_id,
            phase_name=phase_name,
            finding=DeduplicationFinding(
                status=Status.OPEN,
                duplicate_of=None,
                justification="Sole finding in scan and no historical findings.",
            ),
        )
        ctx.state["vulnerabilities"] = vulnerabilities
        await checkpoint_audit_findings(
            vulnerabilities, run_dir, phase_id=phase_id, state=ctx.state
        )
        return vulnerabilities

    model = ctx.state["model"]
    threat_model = ctx.state.get("threat_model_context", "")
    project_summary = ctx.state.get("project_expert_summary", "")

    deduplicator_agent = get_deduplicator_agent(
        model=model,
        threat_model_context=threat_model,
        project_expert_summary=project_summary,
    )

    task_prompt = DEDUPLICATION_TASK_PROMPT_TEMPLATE.format(
        historical_open_json=json.dumps(historical_open, indent=2),
        current_open_json=json.dumps([_serialize_candidate_vuln(v) for v in open_vulns], indent=2),
    )

    try:
        report: DeduplicationReport | None = await run_agent_node(
            ctx,
            deduplicator_agent,
            node_input=task_prompt,
            expected_schema=DeduplicationReport,
            run_id=phase_id,
        )
        _apply_dedup_report(open_vulns, report, phase_id, phase_name)
    except Exception as err:
        logger.error(f"[{phase_id}] DeduplicationAgent failed: {err}")
        for v in open_vulns:
            v.add_skipped(phase_id, phase_name, f"Deduplication failed ({type(err).__name__}).")

    ctx.state["vulnerabilities"] = vulnerabilities
    await checkpoint_audit_findings(vulnerabilities, run_dir, phase_id=phase_id, state=ctx.state)
    logger.info(f"{phase_name} complete.")
    return vulnerabilities
