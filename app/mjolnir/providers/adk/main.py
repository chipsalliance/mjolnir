# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import asyncio
import json
import os
import traceback

from google.adk import Workflow
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from data.vulnerability import Vulnerability
from utilities.logger import logger
from providers.adk.utilities.usage_tracker import LIVE_TRACKER
from providers.adk.phases import (
    initialize,
    audit_phase,
    review_phase,
    ingest_report_phase,
)


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
    logger.write("Initializing ADK 2.0 Workflow Engine...")

    # Build the multi-node workflow graph dynamically
    if ingest_path:
        edges = [
            ("START", initialize),
            (initialize, ingest_report_phase),
            (ingest_report_phase, review_phase),
        ]
    else:
        edges = [
            ("START", initialize),
            (initialize, audit_phase),
            (audit_phase, review_phase),
        ]

    analysis_workflow = Workflow(name="MjolnirAnalysis", edges=edges)

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

    LIVE_TRACKER.__init__()
    LIVE_TRACKER.run_dir = run_dir

    # Run the graph
    status = "Success"
    vulnerabilities: list[Vulnerability] = []
    try:
        for ev in runner.run(
            user_id="mjolnir_user",
            session_id=session.id,
            new_message=user_msg,
        ):
            LIVE_TRACKER.add(ev)
            if ev.node_name == "review_phase" and ev.output is not None:
                vulnerabilities = ev.output
    except (Exception, KeyboardInterrupt) as e:
        logger.error(f"Analysis interrupted or failed: {e}\n{traceback.format_exc()}")
        status = "Failed"

    # Write usage report
    LIVE_TRACKER.write_to_disk(run_dir)

    if not vulnerabilities:
        audit_path = os.path.join(run_dir, "audit_findings.json")
        if os.path.exists(audit_path):
            logger.warning(
                "Falling back to unreviewed Phase 1 vulnerabilities due to Phase 2 interruption."
            )
            try:
                with open(audit_path, "r", encoding="utf-8") as f:
                    raw_vulns = json.load(f)
                for item in raw_vulns:
                    if isinstance(item, dict):
                        vulnerabilities.append(Vulnerability.model_validate(item))
                    elif isinstance(item, Vulnerability):
                        vulnerabilities.append(item)
            except Exception as e:
                logger.error(f"Could not load fallback Phase 1 vulnerabilities: {e}")

    # Ensure all elements in vulnerabilities are validated Pydantic models
    clean_vulns: list[Vulnerability] = []
    for v in vulnerabilities:
        if isinstance(v, dict):
            try:
                clean_vulns.append(Vulnerability.model_validate(v))
            except Exception as e:
                logger.error(f"Failed to validate dict to Vulnerability: {e}")
        elif isinstance(v, Vulnerability):
            clean_vulns.append(v)

    logger.success("Analysis pipeline completed.")
    return clean_vulns, status
