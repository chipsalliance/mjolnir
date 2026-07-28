# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import asyncio
import json
import os
from google.adk import Context
from google.adk.workflow import node
from utilities.logger import logger
from data.audit_finding import AuditFinding
from data.security_report import SecurityReport
from data.vulnerability import Vulnerability
from providers.adk.utilities.async_runner import run_agent_with_backoff
from providers.adk.agents.ingestion import get_ingestion_agent


def _read_json_file_sync(full_path: str):
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def _try_fast_json_ingestion(full_path: str) -> list[Vulnerability] | None:
    """Attempts fast-path loading from a JSON checkpoint file asynchronously."""
    if not (os.path.isfile(full_path) and full_path.endswith(".json")):
        return None

    try:
        data = await asyncio.to_thread(_read_json_file_sync, full_path)
        if not (isinstance(data, list) and data):
            return None

        vulns = [Vulnerability.from_dict(item) for item in data]
        if vulns:
            logger.write(
                f"Fast Ingestion: Loaded {len(vulns)} structured vulnerabilities from JSON checkpoint.",
                stdout=True,
            )
            return vulns
    except Exception as e:
        logger.info(
            f"JSON fast ingestion failed ({e}). Falling back to LLM tool delegation."
        )
    return None


@node(rerun_on_resume=True)
async def ingest_report_phase(ctx: Context, node_input: str) -> list[Vulnerability]:
    """Alternative Phase 1: Ingests and parses unstructured security report findings using tool delegation."""
    logger.write("Starting Ingestion Phase: Parsing report document(s)...", stdout=True)

    report_file_path = node_input
    model = ctx.state["model"]
    code_dir = ctx.state["code_dir"]
    run_dir = ctx.state.get("run_dir")

    if os.path.isabs(report_file_path) or os.path.exists(report_file_path):
        full_path = report_file_path
    else:
        full_path = os.path.join(code_dir, report_file_path)

    # Fast-Path Checkpoint Check (`vulnerabilities.json` or `audit_findings.json`)
    fast_vulns = await _try_fast_json_ingestion(full_path)
    if fast_vulns is not None:
        return fast_vulns

    # Tool Delegation: IngestionAgent autonomously reads the directory/file using its read_file & glob tools
    if os.path.isdir(full_path):
        document_text = (
            f"Ingestion Target Directory: {full_path}\n\n"
            "This target is a directory. Please use your `glob` and `read_file` tools to discover "
            f"and read all report files, spreadsheets, markdown logs, or JSON summaries inside `{full_path}`. "
            "Synthesize every security vulnerability found across these files into your unified SecurityReport output."
        )
    else:
        document_text = (
            f"Ingestion Target Path: {full_path}\n\n"
            f"Please use your `glob` and `read_file` tools to read and inspect `{full_path}` "
            f"(whether it is a markdown report, spreadsheet, log, or summary file) and any secondary attachments in `{code_dir}`. "
            f"Synthesize every security vulnerability found into your unified SecurityReport output."
        )

    ingestion_agent = get_ingestion_agent(model)
    report = await run_agent_with_backoff(
        ctx,
        ingestion_agent,
        node_input=document_text,
        expected_schema=SecurityReport,
        run_id="ingest_report",
    )

    vulns: list[Vulnerability] = []
    if report and hasattr(report, "to_vulnerabilities"):
        vulns = report.to_vulnerabilities(fallback_file_path=report_file_path)

    if run_dir:
        from providers.adk.phases.audit import checkpoint_audit_findings

        await checkpoint_audit_findings(vulns, run_dir, phase_id="1")

    logger.write(
        f"Ingestion complete. Extracted {len(vulns)} vulnerabilities.", stdout=True
    )
    return vulns
