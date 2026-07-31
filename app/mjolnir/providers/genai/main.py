# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

from data.audit_finding import AuditFinding
from data.review_finding import ReviewFinding
from data.status import Status
from data.verdict import Verdict
from data.vulnerability import Vulnerability
from providers.genai.agents.adversarial_reviewer import AdversarialReviewerAgent
from providers.genai.agents.auditor import AuditorAgent
from providers.genai.client import get_client
from utilities.logger import logger


def phase_1_source_file_exploration(
    auditor: AuditorAgent,
    files: list,
    code_dir: str,
    batch_size: int,
) -> list[Vulnerability]:
    """Runs Phase 1: Source File Exploration (Audit) in parallel."""
    all_vulnerabilities = []
    executor = ThreadPoolExecutor(max_workers=batch_size)
    futures = {}

    try:
        for f_path in files:
            full_file_path = Path(code_dir) / f_path
            try:
                contents = full_file_path.read_text(errors="ignore")
                futures[executor.submit(auditor.run, f_path, contents)] = f_path
            except Exception as e:
                logger.error(f"Could not read {f_path}: {e}.")
        pbar = tqdm(
            as_completed(futures),
            total=len(futures),
            desc="Scanning files",
            unit="file",
            leave=True,
        )
        for future in pbar:
            f_path = futures[future]
            pbar.set_description(f"Scanning {f_path}")
            try:
                report = future.result()
                for audit_finding in report.vulnerabilities:
                    vuln = Vulnerability(
                        id=str(uuid.uuid4()),
                        file=f_path,
                        title=audit_finding.title,
                        severity=audit_finding.severity,
                        location=audit_finding.location,
                        description=audit_finding.description,
                        recommendation=audit_finding.recommendation,
                    )
                    vuln.add(
                        phase_id="1",
                        phase_name="Source File Exploration",
                        finding=audit_finding,
                    )
                    all_vulnerabilities.append(vuln)
            except Exception as e:
                logger.error(f"Scanning {f_path} failed: {e}.")
                executor.shutdown(wait=False, cancel_futures=True)
                sys.exit(1)
    finally:
        executor.shutdown(wait=True)

    return all_vulnerabilities


def phase_2_initial_review(
    reviewer: AdversarialReviewerAgent,
    vulnerabilities: list[Vulnerability],
    batch_size: int,
) -> list[Vulnerability]:
    """Runs Phase 2: Initial Review (Adversarial Review) in parallel for OPEN vulnerabilities."""
    logger.info("Pipeline: Adversarial Review.")

    reviewer_executor = ThreadPoolExecutor(max_workers=batch_size)
    reviewer_futures = {}

    # Only review OPEN vulnerabilities
    open_vulns = [v for v in vulnerabilities if v.status == Status.OPEN]
    if not open_vulns:
        logger.info("No open vulnerabilities to review.")
        return vulnerabilities

    try:
        for vuln in open_vulns:
            audit_view = AuditFinding(
                title=vuln.title,
                severity=vuln.severity,
                location=vuln.location,
                description=vuln.description,
                recommendation=vuln.recommendation,
            )
            vuln_json_str = json.dumps(audit_view.model_dump())
            reviewer_futures[reviewer_executor.submit(reviewer.run, vuln_json_str)] = vuln
        reviewer_pbar = tqdm(
            as_completed(reviewer_futures),
            total=len(reviewer_futures),
            desc="Reviewing findings",
            unit="finding",
            leave=True,
        )

        reviewed_ids = set()
        for future in reviewer_pbar:
            orig_vuln = reviewer_futures[future]
            reviewer_pbar.set_description(f"Reviewing {orig_vuln.title[:30]}")
            try:
                review_finding = future.result()
                orig_vuln.add(phase_id="2", phase_name="Initial Review", finding=review_finding)
                reviewed_ids.add(orig_vuln.id)
            except Exception as e:
                logger.error(f"Adversarial review failed for {orig_vuln.title}: {e}.")
                orig_vuln.add_skipped(
                    phase_id="2",
                    phase_name="Initial Review",
                    justification=f"Review failed: {e}",
                )

        # Mark skipped findings (only among the ones we attempted to review)
        for vuln in open_vulns:
            if vuln.id not in reviewed_ids:
                vuln.add_skipped(
                    phase_id="2",
                    phase_name="Initial Review",
                    justification="Omitted by reviewer.",
                )
    finally:
        reviewer_executor.shutdown(wait=True)

    return vulnerabilities


def run_analysis(
    model: str,
    code_dir: str,
    files: list,
    threat_model_context: str,
    run_dir: str,
    batch_size: int,
    ingest_path: str = None,
) -> list:
    """Executes the E2E production GenAI agent loop (scanning, review, merging)."""
    if ingest_path:
        raise NotImplementedError("GenAI provider does not support ingestion mode.")

    client = get_client()
    if not client:
        raise ValueError("GenAI client credentials not set.")

    # Initialize Agents
    auditor = AuditorAgent(client, model, threat_model_context)

    current_dir = Path(__file__).resolve().parent
    adv_prompt_path = current_dir / "prompts" / "adversarial_reviewer.md"
    adv_instruction = "Verify and filter the listed codebase vulnerability findings. Mark false positives as 'False Positive'."
    if adv_prompt_path.exists():
        with open(adv_prompt_path, "r", encoding="utf-8") as f:
            adv_instruction = f.read().strip()
    adv_instruction = adv_instruction + threat_model_context
    reviewer = AdversarialReviewerAgent(client, model, adv_instruction)

    # PHASE 1: Source File Exploration (Audit)
    all_vulnerabilities = phase_1_source_file_exploration(auditor, files, code_dir, batch_size)

    # PHASE 2: Initial Review (Adversarial Review)
    all_vulnerabilities = phase_2_initial_review(reviewer, all_vulnerabilities, batch_size)

    logger.success("Analysis pipeline completed.")
    return all_vulnerabilities, "Success"
