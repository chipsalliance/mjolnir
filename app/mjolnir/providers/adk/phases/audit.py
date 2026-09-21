# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import asyncio
import json
from pathlib import Path

from google.adk import Context
from google.adk.workflow import node

from constants import PHASE_1_ID
from data.security_report import SecurityReport
from data.vulnerability import Vulnerability
from providers.adk.agents.auditor import (
    AUDITOR_TOOLS,
    build_auditor_instruction,
    get_auditor_agent,
)
from providers.adk.utilities.async_runner import (
    run_agent_node,
    run_batch_with_concurrency,
)
from providers.adk.utilities.cache_manager import PhaseContextCache
from utilities.git import get_file_diff_async
from utilities.logger import logger


def _write_checkpoint_sync(audit_path: Path, vulns_data: list[dict]) -> None:
    with open(audit_path, "w") as f:
        json.dump(vulns_data, f, indent=2)


async def _read_file_contents_async(full_file_path: Path) -> str:
    return await asyncio.to_thread(full_file_path.read_text, encoding="utf-8", errors="ignore")


async def checkpoint_audit_findings(
    vulns: list[Vulnerability],
    run_dir: str,
    phase_id: str = PHASE_1_ID,
    filename: str = None,
) -> None:
    """Checkpoints audit findings to a JSON file on disk without blocking the event loop."""
    if not run_dir or not Path(run_dir).exists():
        return
    checkpoint_name = filename or f"finding_phase_{phase_id}.json"
    audit_path = Path(run_dir) / checkpoint_name
    try:
        vulns_data = [v.model_dump() for v in vulns]
        await asyncio.to_thread(_write_checkpoint_sync, audit_path, vulns_data)
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
    project_summary = ctx.state.get("project_expert_summary", "")
    batch_size = ctx.state["batch_size"]
    run_dir = ctx.state.get("run_dir")

    auditor_instruction = build_auditor_instruction(threat_model, project_summary)

    with PhaseContextCache(
        model=model,
        instruction=auditor_instruction,
        tools=AUDITOR_TOOLS,
        output_schema=SecurityReport,
        display_name=f"mjolnir-phase1-{Path(code_dir).name}",
    ) as cache:
        auditor_agent = get_auditor_agent(
            model, threat_model, project_summary, cached_content=cache.cache_name
        )

        diff_base = ctx.state.get("diff_base")
        diff_head = ctx.state.get("diff_head")

        async def audit_single_file(f_path: str) -> list[Vulnerability]:
            full_file_path = Path(code_dir) / f_path
            try:
                contents = await _read_file_contents_async(full_file_path)
            except Exception as e:
                logger.error(f"Could not read {f_path}: {e}")
                return []

            if diff_base:
                file_diff = await get_file_diff_async(
                    code_dir, diff_base, diff_head or "HEAD", f_path
                )
                diff_section = (
                    f"\n\n### Pull Request Diff (Changes Under Review):\n```diff\n{file_diff}\n```"
                    if file_diff
                    else ""
                )
                node_input = (
                    f"Filename: {f_path}\n"
                    f"Mode: Pull Request Diff Security Review"
                    f"{diff_section}\n\n"
                    f"### Full File Content:\n{contents}"
                )
            else:
                node_input = f"Filename: {f_path}\n\n### Full File Content:\n{contents}"

            report = await run_agent_node(
                ctx,
                auditor_agent,
                node_input=node_input,
                expected_schema=SecurityReport,
                run_id=f_path,
            )

            if report is None:
                logger.warning(
                    f"AuditorAgent returned no report for '{f_path}' "
                    "(potential refusal, timeout, or schema validation failure)."
                )
                return []

            if not hasattr(report, "vulnerabilities") or not report.vulnerabilities:
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
