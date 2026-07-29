# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import asyncio
import json
import os
import traceback
from pathlib import Path

from google.adk import Workflow
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from data.vulnerability import Vulnerability
from utilities.logger import logger
from providers.adk.utilities.usage_tracker import UsageTracker
from providers.adk.phases import (
    initialize,
    audit_phase,
    review_phase,
    ingest_report_phase,
)


def build_audit_workflow(name: str = "MjolnirAuditWorkflow") -> Workflow:
    """Factory builder for standard discovery and audit workflow graph."""
    edges = [
        ("START", initialize),
        (initialize, audit_phase),
        (audit_phase, review_phase),
    ]
    return Workflow(name=name, edges=edges)


def build_ingest_workflow(name: str = "MjolnirIngestWorkflow") -> Workflow:
    """Factory builder for report ingestion workflow graph."""
    edges = [
        ("START", initialize),
        (initialize, ingest_report_phase),
        (ingest_report_phase, review_phase),
    ]
    return Workflow(name=name, edges=edges)


def build_analysis_workflow(
    ingest_path: str | None = None, name: str = "MjolnirAnalysis"
) -> Workflow:
    """Builds a multi-node workflow graph based on execution parameters."""
    if ingest_path:
        return build_ingest_workflow(name=name)
    return build_audit_workflow(name=name)


def run_analysis(
    model: str,
    code_dir: str,
    files: list,
    threat_model_context: str,
    run_dir: str,
    batch_size: int,
    ingest_path: str = None,
) -> tuple[list[Vulnerability], str]:
    """ADK 2.0 provider pipeline: executes a multi-node workflow graph."""
    logger.info("Initializing ADK 2.0 Workflow Engine...")

    # Build the multi-node workflow graph dynamically via workflow builders
    analysis_workflow = build_analysis_workflow(ingest_path=ingest_path)

    session_service = InMemorySessionService()
    runner = Runner(
        agent=analysis_workflow,
        app_name="mjolnir",
        session_service=session_service,
    )

    session = asyncio.run(
        session_service.create_session(
            app_name="mjolnir",
            user_id="mjolnir_user",
        )
    )

    usage_tracker = UsageTracker(run_dir=run_dir)
    initial_state = {
        "model": model,
        "code_dir": code_dir,
        "threat_model_context": threat_model_context,
        "batch_size": batch_size,
        "ingest_path": ingest_path,
        "run_dir": run_dir,
        "usage_tracker": usage_tracker,
    }

    workflow_input = {
        "model": model,
        "code_dir": code_dir,
        "files": files,
        "threat_model_context": threat_model_context,
        "batch_size": batch_size,
        "ingest_path": ingest_path,
        "run_dir": run_dir,
    }

    user_msg = types.Content(
        role="user",
        parts=[types.Part.from_text(text=json.dumps(workflow_input))],
    )

    # Run the graph
    status = "Success"
    vulnerabilities: list[Vulnerability] = []
    try:
        for ev in runner.run(
            user_id="mjolnir_user",
            session_id=session.id,
            new_message=user_msg,
        ):
            usage_tracker.add(ev)
            if ev.node_name == "review_phase" and ev.output is not None:
                vulnerabilities = ev.output
    except (Exception, KeyboardInterrupt) as e:
        logger.error(f"Analysis interrupted or failed: {e}\n{traceback.format_exc()}")
        status = "Failed"

    # Write usage report
    usage_tracker.write_to_disk(run_dir)

    if not vulnerabilities and run_dir:
        audit_path = Path(run_dir) / "finding_phase_1.json"
        if not audit_path.exists():
            audit_path = Path(run_dir) / "audit_findings.json"

        if audit_path.exists():
            logger.warning(
                "Falling back to unreviewed Phase 1 vulnerabilities due to Phase 2 interruption."
            )
            try:
                with open(audit_path, "r", encoding="utf-8") as f:
                    raw_vulns = json.load(f)
                if isinstance(raw_vulns, list):
                    vulnerabilities = raw_vulns
            except Exception as e:
                logger.error(f"Could not load fallback Phase 1 vulnerabilities: {e}")

    # Ensure all elements in vulnerabilities are validated Pydantic models
    clean_vulns: list[Vulnerability] = []
    for item in vulnerabilities:
        try:
            clean_vulns.append(Vulnerability.from_dict(item))
        except Exception as e:
            logger.error(f"Failed to validate item to Vulnerability: {e}")

    logger.success("Analysis pipeline completed.")
    return clean_vulns, status
