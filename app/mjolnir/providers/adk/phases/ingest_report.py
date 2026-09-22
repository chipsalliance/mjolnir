# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import asyncio
import json
from pathlib import Path
from typing import Union

from google.adk import Context
from google.adk.workflow import node

from constants import (
    INGEST_DIR_TASK_PROMPT_TEMPLATE,
    INGEST_FILE_TASK_PROMPT_TEMPLATE,
    PHASE_INGEST_ID,
    PHASE_INGEST_NAME,
)
from data.security_report import SecurityReport
from data.vulnerability import Vulnerability
from providers.adk.agents.ingestion import get_ingestion_agent
from providers.adk.phases.audit import checkpoint_audit_findings
from providers.adk.utilities.async_runner import run_agent_node
from utilities.logger import logger


def _read_json_file_sync(full_path: Path):
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def _try_fast_json_ingestion(full_path: Path) -> list[Vulnerability] | None:
    """Attempts fast-path loading from a JSON checkpoint file asynchronously."""
    if not (full_path.is_file() and full_path.suffix == ".json"):
        return None

    try:
        data = await asyncio.to_thread(_read_json_file_sync, full_path)
        if not (isinstance(data, list) and data):
            return None

        vulns = [
            Vulnerability.from_dict(
                item,
                phase_id=PHASE_INGEST_ID,
                phase_name=PHASE_INGEST_NAME,
            )
            for item in data
        ]
        if vulns:
            logger.info(
                f"Fast Ingestion: Loaded {len(vulns)} structured vulnerabilities from JSON checkpoint."
            )
            return vulns
    except Exception as e:
        logger.info(f"JSON fast ingestion failed ({e}). Falling back to LLM tool delegation.")
    return None


@node(rerun_on_resume=True)
async def ingest_report_phase(ctx: Context, node_input: str | None = None) -> list[Vulnerability]:
    """Ingests and parses unstructured security report findings using tool delegation."""
    logger.info(f"Starting {PHASE_INGEST_NAME} ({PHASE_INGEST_ID}): Parsing report document(s)...")

    report_file_path = (
        node_input
        if isinstance(node_input, str) and node_input
        else ctx.state.get("ingest_path", "")
    )
    model = ctx.state["model"]
    code_dir = ctx.state["code_dir"]
    run_dir = ctx.state.get("run_dir")

    report_path = Path(report_file_path)
    if report_path.is_absolute() or report_path.exists():
        full_path = report_path
    else:
        full_path = Path(code_dir) / report_file_path

    # Fast-Path Checkpoint Check (`vulnerabilities.json` or `audit_findings.json`)
    fast_vulns = await _try_fast_json_ingestion(full_path)
    if fast_vulns is not None:
        ctx.state["vulnerabilities"] = fast_vulns
        return fast_vulns

    # Tool Delegation: IngestionAgent autonomously reads the directory/file using its read_file & glob tools
    if full_path.is_dir():
        document_text = INGEST_DIR_TASK_PROMPT_TEMPLATE.format(full_path=full_path)
    else:
        document_text = INGEST_FILE_TASK_PROMPT_TEMPLATE.format(
            full_path=full_path, code_dir=code_dir
        )

    ingestion_agent = get_ingestion_agent(model)
    report = await run_agent_node(
        ctx,
        ingestion_agent,
        node_input=document_text,
        expected_schema=SecurityReport,
        run_id=PHASE_INGEST_ID,
    )

    vulns: list[Vulnerability] = []
    if report and hasattr(report, "to_vulnerabilities"):
        vulns = report.to_vulnerabilities(
            fallback_file_path=report_file_path,
            phase_id=PHASE_INGEST_ID,
            phase_name=PHASE_INGEST_NAME,
        )

    ctx.state["vulnerabilities"] = vulns
    if run_dir:
        await checkpoint_audit_findings(vulns, run_dir, phase_id=PHASE_INGEST_ID, state=ctx.state)

    logger.info(f"{PHASE_INGEST_NAME} complete. Extracted {len(vulns)} vulnerabilities.")
    return vulns
