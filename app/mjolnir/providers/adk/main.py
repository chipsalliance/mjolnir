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

from constants import (
    PHASE_DISCOVERY_ID,
    PHASE_EXPLORATION_ID,
    PHASE_FINAL_REVIEW_ID,
    PHASE_INGEST_ID,
    PHASE_INITIAL_REVIEW_ID,
    PHASE_POC_CREATION_ID,
    PIPELINE_MODE_FAST,
    PIPELINE_MODE_FULL,
)
from data.vulnerability import Vulnerability
from providers.adk.phases import (
    discovery_phase,
    final_review_phase,
    ingest_report_phase,
    initial_review_phase,
    initialize,
    poc_creation_phase,
    project_exploration_phase,
)
from providers.adk.utilities.usage_tracker import UsageTracker
from utilities.logger import logger

PHASE_REGISTRY = {
    PHASE_EXPLORATION_ID: project_exploration_phase,
    PHASE_DISCOVERY_ID: discovery_phase,
    PHASE_INGEST_ID: ingest_report_phase,
    PHASE_INITIAL_REVIEW_ID: initial_review_phase,
    PHASE_POC_CREATION_ID: poc_creation_phase,
    PHASE_FINAL_REVIEW_ID: final_review_phase,
}


def build_composable_workflow(
    phase_ids: list[str], name: str = "MjolnirComposableWorkflow"
) -> Workflow:
    """Builds a workflow graph from an arbitrary ordered list of registered phase IDs."""
    nodes = []
    for pid in phase_ids:
        if pid not in PHASE_REGISTRY:
            raise ValueError(
                f"Unknown phase ID '{pid}'. Available phases: {list(PHASE_REGISTRY.keys())}"
            )
        nodes.append(PHASE_REGISTRY[pid])

    edges = []
    prev = initialize
    edges.append(("START", initialize))
    for phase_node in nodes:
        edges.append((prev, phase_node))
        prev = phase_node
    return Workflow(name=name, edges=edges)


def resolve_mode_phases(mode: str, ingest_path: str | None = None) -> list[str]:
    """Resolves the ordered phase IDs for 'fast' (classic discovery + initial review) or 'full' mode."""
    entry_phase = PHASE_INGEST_ID if ingest_path else PHASE_DISCOVERY_ID
    if mode == PIPELINE_MODE_FULL:
        return [
            PHASE_EXPLORATION_ID,
            entry_phase,
            PHASE_INITIAL_REVIEW_ID,
            PHASE_POC_CREATION_ID,
            PHASE_FINAL_REVIEW_ID,
        ]
    if mode == PIPELINE_MODE_FAST:
        return [entry_phase, PHASE_INITIAL_REVIEW_ID]
    raise ValueError(f"Unsupported pipeline mode: '{mode}'")


def build_audit_workflow(mode: str, name: str = "MjolnirAuditWorkflow") -> Workflow:
    """Factory builder for discovery and review workflow graph."""
    return build_composable_workflow(
        resolve_mode_phases(mode=mode, ingest_path=None),
        name=name,
    )


def build_ingest_workflow(mode: str, name: str = "MjolnirIngestWorkflow") -> Workflow:
    """Factory builder for report ingestion workflow graph."""
    return build_composable_workflow(
        resolve_mode_phases(mode=mode, ingest_path="ingest"),
        name=name,
    )


def build_analysis_workflow(
    mode: str,
    ingest_path: str | None = None,
    name: str = "MjolnirAnalysis",
) -> Workflow:
    """Builds a multi-node workflow graph based on pipeline mode ('fast' or 'full') and ingestion state."""
    if ingest_path:
        return build_ingest_workflow(mode=mode, name=name)
    return build_audit_workflow(mode=mode, name=name)


def _is_vulnerability_list(output: object) -> bool:
    """Returns True if a node output represents a list of Vulnerability objects/dicts."""
    if not isinstance(output, list):
        return False
    if not output:
        return True
    first = output[0]
    return isinstance(first, Vulnerability) or (
        isinstance(first, dict) and ("title" in first or "audit_finding" in first)
    )


def _find_fallback_checkpoint(run_dir: str, state: dict) -> Path | None:
    """Locates the most recent vulnerability checkpoint written before an interruption."""
    last_cp = state.get("last_checkpoint_path")
    if last_cp and Path(last_cp).exists():
        return Path(last_cp)

    run_path = Path(run_dir)
    candidates = [
        run_path / f"finding_phase_{PHASE_DISCOVERY_ID}.json",
        run_path / f"finding_phase_{PHASE_INGEST_ID}.json",
        run_path / "audit_findings.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def run_analysis(
    model: str,
    code_dir: str,
    files: list,
    threat_model_context: str,
    run_dir: str,
    batch_size: int,
    mode: str,
    ingest_path: str = None,
    diff_base: str = None,
    diff_head: str = None,
    min_poc_severity: str = "Medium",
) -> tuple[list[Vulnerability], str]:
    """ADK 2.0 provider pipeline: executes a multi-node workflow graph."""
    logger.info(f"Initializing ADK 2.0 Workflow Engine (mode={mode})...")

    try:
        from google.adk.models.google_llm import Gemini

        client_backend = Gemini(model=model).api_client._api_client
        if client_backend.vertexai:
            logger.success(
                f"Using Vertex AI for ADK engine (project={client_backend.project}, location={client_backend.location})"
            )
        else:
            logger.success("Using Gemini API Key for ADK engine")
    except Exception as e:
        logger.warning(f"Could not inspect ADK client metadata: {e}")

    enable_project_expert = mode == PIPELINE_MODE_FULL
    analysis_workflow = build_analysis_workflow(mode=mode, ingest_path=ingest_path)

    session_service = InMemorySessionService()
    runner = Runner(
        agent=analysis_workflow,
        app_name="mjolnir",
        session_service=session_service,
    )

    usage_tracker = UsageTracker(run_dir=run_dir)
    initial_state = {
        "model": model,
        "code_dir": code_dir,
        "files": files,
        "threat_model_context": threat_model_context,
        "batch_size": batch_size,
        "ingest_path": ingest_path,
        "diff_base": diff_base,
        "diff_head": diff_head,
        "run_dir": run_dir,
        "mode": mode,
        "min_poc_severity": min_poc_severity,
        "enable_project_expert": enable_project_expert,
        "usage_tracker": usage_tracker,
        "project_expert_qa_history": [],
        "vulnerabilities": [],
    }

    session = asyncio.run(
        session_service.create_session(
            app_name="mjolnir",
            user_id="mjolnir_user",
            state=initial_state,
        )
    )

    workflow_input = {
        "model": model,
        "code_dir": code_dir,
        "files": files,
        "threat_model_context": threat_model_context,
        "batch_size": batch_size,
        "ingest_path": ingest_path,
        "diff_base": diff_base,
        "diff_head": diff_head,
        "run_dir": run_dir,
        "mode": mode,
        "min_poc_severity": min_poc_severity,
        "enable_project_expert": enable_project_expert,
    }

    user_msg = types.Content(
        role="user",
        parts=[types.Part.from_text(text=json.dumps(workflow_input))],
    )

    # Run the graph and capture the latest vulnerability list emitted by any phase node
    status = "Success"
    vulnerabilities: list[Vulnerability] | None = None
    try:
        for ev in runner.run(
            user_id="mjolnir_user",
            session_id=session.id,
            new_message=user_msg,
        ):
            usage_tracker.add(ev)
            if (
                ev.node_name not in ("START", "initialize", "project_exploration_phase")
                and ev.output is not None
                and _is_vulnerability_list(ev.output)
            ):
                vulnerabilities = ev.output
    except (Exception, KeyboardInterrupt) as e:
        logger.error(f"Analysis interrupted or failed: {e}\n{traceback.format_exc()}")
        status = "Failed"

    # Write usage report
    usage_tracker.write_to_disk(run_dir)

    # Fall back to the most recent phase checkpoint if the workflow was interrupted
    if vulnerabilities is None and run_dir:
        checkpoint_path = _find_fallback_checkpoint(run_dir, initial_state)
        if checkpoint_path:
            logger.warning(
                f"Falling back to checkpointed vulnerabilities at {checkpoint_path} due to pipeline interruption."
            )
            try:
                with open(checkpoint_path, "r", encoding="utf-8") as f:
                    raw_vulns = json.load(f)
                if isinstance(raw_vulns, list):
                    vulnerabilities = raw_vulns
            except Exception as e:
                logger.error(f"Could not load fallback vulnerabilities: {e}")

    if vulnerabilities is None:
        vulnerabilities = []

    # Ensure all elements in vulnerabilities are validated Pydantic models
    clean_vulns: list[Vulnerability] = []
    for item in vulnerabilities:
        try:
            clean_vulns.append(Vulnerability.from_dict(item))
        except Exception as e:
            logger.error(f"Failed to validate item to Vulnerability: {e}")

    logger.success("Analysis pipeline completed.")
    return clean_vulns, status
