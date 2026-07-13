# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
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


@node(rerun_on_resume=True)
async def ingest_report_phase(ctx: Context, node_input: str) -> list[Vulnerability]:
    """Alternative Phase 1: Ingests and parses unstructured security report findings using tool delegation."""
    logger.write("Starting Ingestion Phase: Parsing report document(s)...", stdout=True)

    report_file_path = node_input
    model = ctx.state["model"]
    code_dir = ctx.state["code_dir"]
    run_dir = ctx.state.get("run_dir")
    full_path = os.path.join(code_dir, report_file_path)
    if not os.path.exists(full_path) and os.path.exists(report_file_path):
        full_path = report_file_path

    # Fast-Path Checkpoint Check (`vulnerabilities.json` or `audit_findings.json`)
    if os.path.isfile(full_path) and full_path.endswith(".json"):
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                vulns: list[Vulnerability] = []
                for item in data:
                    if isinstance(item, dict) and "history" in item and "id" in item:
                        vulns.append(Vulnerability.model_validate(item))
                    else:
                        raw_af = item.get("audit_finding", item)
                        af = AuditFinding.model_validate(raw_af)
                        target_file = af.file or item.get(
                            "file", item.get("location", "unknown_file")
                        )
                        vulns.append(
                            Vulnerability.from_audit_finding(af, file_path=target_file)
                        )
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

    # Tool Delegation: IngestionAgent autonomously reads the directory/file using its read_file & glob tools
    if os.path.isdir(full_path):
        document_text = (
            f"Ingestion Target Directory: {full_path}\n\n"
            f"This target is a directory. Please use your `glob` and `read_file` tools to discover "
            f"and read all report files, spreadsheets, markdown logs, or JSON summaries inside `{full_path}`. "
            f"Synthesize every security vulnerability found across these files into your unified SecurityReport output."
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
    if report and hasattr(report, "vulnerabilities") and report.vulnerabilities:
        for af in report.vulnerabilities:
            target_file = (
                af.file if af.file and af.file != "unknown_file" else report_file_path
            )
            if os.path.isdir(full_path) and (not af.file or af.file == "unknown_file"):
                target_file = "unknown_file"
            vulns.append(Vulnerability.from_audit_finding(af, file_path=target_file))

    if run_dir:
        audit_path = os.path.join(run_dir, "audit_findings.json")
        try:
            with open(audit_path, "w") as f:
                json.dump([v.model_dump() for v in vulns], f, indent=2)
            logger.write(
                f"Checkpointed {len(vulns)} Phase 1 vulnerabilities to {audit_path}"
            )
        except Exception as e:
            logger.error(f"Failed to checkpoint Phase 1 vulnerabilities: {e}")

    logger.write(
        f"Ingestion complete. Extracted {len(vulns)} vulnerabilities.", stdout=True
    )
    return vulns
