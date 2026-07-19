# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import json
import os
from google.adk import Context
from google.adk.workflow import node
from utilities.logger import logger
from data.security_report import SecurityReport
from data.vulnerability import Vulnerability
from providers.adk.utilities.async_runner import (
    run_agent_with_backoff,
    run_batch_with_concurrency,
)
from providers.adk.agents.auditor import get_auditor_agent


def checkpoint_audit_findings(vulns: list[Vulnerability], run_dir: str | None) -> None:
    """Serializes and checkpoints Phase 1 vulnerability findings to disk."""
    if not run_dir:
        return
    audit_path = os.path.join(run_dir, "audit_findings.json")
    try:
        with open(audit_path, "w") as f:
            json.dump([v.model_dump() for v in vulns], f, indent=2)
        logger.write(
            f"Checkpointed {len(vulns)} Phase 1 vulnerabilities to {audit_path}"
        )
    except Exception as e:
        logger.error(f"Failed to checkpoint Phase 1 vulnerabilities: {e}")


@node(rerun_on_resume=True)
async def audit_phase(ctx: Context, node_input: list[str]) -> list[Vulnerability]:
    """Phase 1: Dynamic File Auditing (Discovery)."""
    logger.write("Starting Phase 1: Exploration Audits...", stdout=True)

    model = ctx.state["model"]
    code_dir = ctx.state["code_dir"]
    threat_model = ctx.state["threat_model_context"]
    batch_size = ctx.state["batch_size"]
    run_dir = ctx.state.get("run_dir")

    auditor_agent = get_auditor_agent(model, threat_model)

    async def audit_single_file(f_path: str) -> list[Vulnerability]:
        full_file_path = os.path.join(code_dir, f_path)
        try:
            with open(full_file_path, "r", errors="ignore") as f:
                contents = f.read()
        except Exception as e:
            logger.error(f"Could not read {f_path}: {e}")
            return []

        run_id = f"audit_{f_path.replace('/', '_').replace('.', '_')}"
        report = await run_agent_with_backoff(
            ctx,
            auditor_agent,
            node_input=f"Filename: {f_path}\n\nContent:\n{contents}",
            expected_schema=SecurityReport,
            run_id=run_id,
        )
        if (
            not report
            or not hasattr(report, "vulnerabilities")
            or not report.vulnerabilities
        ):
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
    )

    if exceptions:
        logger.write(
            f"WARNING: Phase 1 encountered {len(exceptions)} fatal errors. Sample failure: {exceptions[0]}",
            stdout=True,
        )
        logger.error(f"Phase 1 errors: {exceptions[0]}", exc_info=exceptions[0])

    flat_vulns = [vuln for file_vulns in results for vuln in file_vulns]
    checkpoint_audit_findings(flat_vulns, run_dir)

    logger.write(
        f"Phase 1 complete. Found {len(flat_vulns)} total vulnerabilities.", stdout=True
    )
    return flat_vulns
