# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import asyncio
import json
from pathlib import Path

from google.adk import Context
from google.adk.workflow import node

from agent_tools.ast_search import ast_search
from agent_tools.ctags_search import ctags_search
from agent_tools.glob import glob
from agent_tools.grep_search import grep_search
from agent_tools.read_file import read_file
from data.security_report import SecurityReport
from data.vulnerability import Vulnerability
from providers.adk.agents.auditor import build_auditor_instruction, get_auditor_agent
from providers.adk.utilities.async_runner import (
    run_agent_node,
    run_batch_with_concurrency,
)
from providers.adk.utilities.cache_manager import PhaseContextCache
from utilities.logger import logger


def _write_checkpoint_sync(audit_path: Path, vulns_data: list[dict]) -> None:
    with open(audit_path, "w") as f:
        json.dump(vulns_data, f, indent=2)


def _read_file_contents_sync(full_file_path: Path) -> str:
    with open(full_file_path, "r", errors="ignore") as f:
        return f.read()


async def checkpoint_audit_findings(
    vulns: list[Vulnerability],
    run_dir: str,
    phase_id: int = 1,
    filename: str = None,
) -> None:
    """Checkpoints audit findings to a JSON file on disk."""
    if not run_dir or not Path(run_dir).exists():
        return
    checkpoint_name = filename or f"finding_phase_{phase_id}.json"
    audit_path = Path(run_dir) / checkpoint_name
    try:
        vulns_data = [v.model_dump() for v in vulns]
        _write_checkpoint_sync(audit_path, vulns_data)
        logger.info(f"Checkpointed {len(vulns)} Phase {phase_id} vulnerabilities to {audit_path}")
    except Exception as e:
        logger.error(f"Failed to checkpoint Phase {phase_id} vulnerabilities: {e}")


@node(rerun_on_resume=True)
async def audit_phase(ctx: Context, node_input: list[str]) -> list[Vulnerability]:
    """Phase 1: Dynamic File Auditing (Discovery)."""
    logger.info("Starting Phase 1: Exploration Audits...")

    model = ctx.state["model"]
    code_dir = ctx.state["code_dir"]
    threat_model = ctx.state["threat_model_context"]
    batch_size = ctx.state["batch_size"]
    run_dir = ctx.state.get("run_dir")

    auditor_tools = [read_file, glob, grep_search, ctags_search, ast_search]
    auditor_instruction = build_auditor_instruction(threat_model)

    with PhaseContextCache(
        model=model,
        instruction=auditor_instruction,
        tools=auditor_tools,
        display_name=f"mjolnir-phase1-{Path(code_dir).name}",
    ) as cache:
        auditor_agent = get_auditor_agent(model, threat_model, cached_content=cache.cache_name)

        async def audit_single_file(f_path: str) -> list[Vulnerability]:
            full_file_path = Path(code_dir) / f_path
            try:
                contents = _read_file_contents_sync(full_file_path)
            except Exception as e:
                logger.error(f"Could not read {f_path}: {e}")
                return []

            run_id = f"audit_{f_path.replace('/', '_').replace('.', '_')}"
            report = await run_agent_node(
                ctx,
                auditor_agent,
                node_input=f"Filename: {f_path}\n\nContent:\n{contents}",
                expected_schema=SecurityReport,
                run_id=run_id,
            )

            if not report or not hasattr(report, "vulnerabilities") or not report.vulnerabilities:
                return []

            vulns: list[Vulnerability] = []
            for af in report.vulnerabilities:
                af.file = f_path
                vulns.append(Vulnerability.from_audit_finding(af, file_path=f_path))
            return vulns

        results, exceptions = await run_batch_with_concurrency(
            items=node_input,
            worker_fn=audit_single_file,
            concurrency_limit=batch_size,
            desc="Scanning files",
            unit="file",
            usage_tracker=ctx.state.get("usage_tracker"),
        )

    if exceptions:
        logger.warning(f"Phase 1 encountered {len(exceptions)} fatal errors.")
        for exc in exceptions:
            logger.error(f"Phase 1 error: {exc}", exc_info=exc)

    flat_vulns = [vuln for file_vulns in results for vuln in file_vulns]
    await checkpoint_audit_findings(flat_vulns, run_dir)

    logger.info(f"Phase 1 complete. Found {len(flat_vulns)} total vulnerabilities.")

    return flat_vulns
