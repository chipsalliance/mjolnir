# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import json
import os
import uuid

from tqdm import tqdm

from constants import (
    PHASE_DISCOVERY_ID,
    PHASE_DISCOVERY_NAME,
    PHASE_FINAL_REVIEW_ID,
    PHASE_FINAL_REVIEW_NAME,
    PHASE_INITIAL_REVIEW_ID,
    PHASE_INITIAL_REVIEW_NAME,
    PHASE_POC_CREATION_ID,
    PHASE_POC_CREATION_NAME,
    PIPELINE_MODE_FULL,
    PROJECT_EXPERT_SUMMARY_FILENAME,
)
from data.audit_finding import AuditFinding
from data.exploit_finding import ExploitFinding
from data.review_finding import ReviewFinding
from data.severity import Severity
from data.status import Status
from data.verdict import Verdict
from data.vulnerability import Vulnerability
from utilities.logger import logger


def run_analysis(
    model: str,
    code_dir: str,
    files: list,
    threat_model_context: str,
    run_dir: str,
    batch_size: int,
    mode: str,
    ingest_path: str = None,
    min_poc_severity: str = "Medium",
) -> list:
    """Instantly returns hardcoded mock findings and compiles a mock flow history for testing."""

    if mode == PIPELINE_MODE_FULL:
        logger.info("Executing initial project exploration (Project Expert - Mock)...")
        if threat_model_context:
            logger.debug("Project Expert ingested threat model context.")
        if run_dir:
            summary_path = os.path.join(run_dir, PROJECT_EXPERT_SUMMARY_FILENAME)
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write("# Project Expert Summary (Mock)\n\nMock project architecture summary.\n")

    all_vulnerabilities = []

    pbar = tqdm(files, desc="\tScanning files", unit="file")
    for idx, f_path in enumerate(pbar):
        pbar.set_description(f"\tScanning {f_path} (Mock)")
        ext = os.path.splitext(f_path)[1].lstrip(".").lower()
        prompt_name = "rust_auditor.md" if ext == "rs" else "c_auditor.md"

        logger.debug(f"Scanning {f_path} (Mock)...")
        logger.debug(f"Loaded prompt for .{ext} from: {prompt_name}")

        fid = str(uuid.uuid4())

        # 1. Discovery Finding
        audit_finding = AuditFinding(
            title="Mock Vulnerability",
            severity=Severity.MEDIUM,
            location="Line 42",
            description=f"Mock vulnerability flagged for file '{f_path}' by model '{model}'.",
            recommendation="Replace mock config with production backend.",
        )

        vuln = Vulnerability(
            id=fid,
            file=f_path,
            title=audit_finding.title,
            severity=audit_finding.severity,
            location=audit_finding.location,
            description=audit_finding.description,
            recommendation=audit_finding.recommendation,
        )
        vuln.add(
            phase_id=PHASE_DISCOVERY_ID,
            phase_name=PHASE_DISCOVERY_NAME,
            finding=audit_finding,
        )

        # 2. Simulate Initial Review
        # We vary status to test all flow branches (kept, downgraded, FP/discarded, skipped/kept)
        case = idx % 4

        if case == 0:
            # Finding survives intact
            review = ReviewFinding(
                title=audit_finding.title,
                severity=Severity.MEDIUM,
                location=audit_finding.location,
                description=audit_finding.description,
                recommendation=audit_finding.recommendation,
                verdict=Verdict.EXPLOITABLE,
                justification="Testing intact path.",
                attack_vector="Trigger exploit directly.",
            )
            vuln.add(
                phase_id=PHASE_INITIAL_REVIEW_ID,
                phase_name=PHASE_INITIAL_REVIEW_NAME,
                finding=review,
            )
        elif case == 1:
            # Finding is downgraded
            review = ReviewFinding(
                title="Mock Vulnerability (Downgraded)",
                severity=Severity.LOW,
                location=audit_finding.location,
                description="Refined description for low severity.",
                recommendation=audit_finding.recommendation,
                verdict=Verdict.NOT_EXPLOITABLE,
                justification="Testing downgrade path.",
                attack_vector="",
            )
            vuln.add(
                phase_id=PHASE_INITIAL_REVIEW_ID,
                phase_name=PHASE_INITIAL_REVIEW_NAME,
                finding=review,
            )
        elif case == 2:
            # Finding is resolved as False Positive (Discarded)
            review = ReviewFinding(
                title=audit_finding.title,
                severity=Severity.MEDIUM,
                location=audit_finding.location,
                description=audit_finding.description,
                recommendation=audit_finding.recommendation,
                verdict=Verdict.FALSE_POSITIVE,
                justification="Testing false positive path.",
                attack_vector="",
            )
            vuln.add(
                phase_id=PHASE_INITIAL_REVIEW_ID,
                phase_name=PHASE_INITIAL_REVIEW_NAME,
                finding=review,
            )
        else:
            # Finding is skipped (Omitted by reviewer -> Kept via fail-open)
            vuln.add_skipped(
                phase_id=PHASE_INITIAL_REVIEW_ID,
                phase_name=PHASE_INITIAL_REVIEW_NAME,
                justification="Omitted during mock review simulation.",
            )

        # 3 & 4. Simulate PoC Creation & Final Review in full mode
        if mode == PIPELINE_MODE_FULL:
            if vuln.status != Status.OPEN:
                vuln.add_skipped(
                    phase_id=PHASE_POC_CREATION_ID,
                    phase_name=PHASE_POC_CREATION_NAME,
                    justification=f"Skipped: Status is {vuln.status}",
                )
                vuln.add_skipped(
                    phase_id=PHASE_FINAL_REVIEW_ID,
                    phase_name=PHASE_FINAL_REVIEW_NAME,
                    justification=f"Skipped: Status is {vuln.status}",
                )
            elif not vuln.severity.meets_threshold(min_poc_severity):
                vuln.add_skipped(
                    phase_id=PHASE_POC_CREATION_ID,
                    phase_name=PHASE_POC_CREATION_NAME,
                    justification=f"Skipped: Severity ({vuln.severity.value}) is below minimum PoC threshold ({min_poc_severity}).",
                )
                vuln.add_skipped(
                    phase_id=PHASE_FINAL_REVIEW_ID,
                    phase_name=PHASE_FINAL_REVIEW_NAME,
                    justification="Skipped: No PoC generated for this finding.",
                )
            else:
                exploit_finding = ExploitFinding(
                    poc="```rust\n#[test]\nfn test_mock_poc() { assert_eq!(1, 1); }\n```",
                    test_command="cargo test test_mock_poc",
                    test_output="running 1 test\ntest test_mock_poc ... ok",
                    poc_verified=True,
                    justification="Mock PoC synthesized and verified in isolated worktree.",
                )
                vuln.add(
                    phase_id=PHASE_POC_CREATION_ID,
                    phase_name=PHASE_POC_CREATION_NAME,
                    finding=exploit_finding,
                )

                final_review = ReviewFinding(
                    title=vuln.title,
                    severity=vuln.severity,
                    location=vuln.location,
                    description=vuln.description,
                    recommendation=vuln.recommendation,
                    verdict=vuln.verdict or Verdict.EXPLOITABLE,
                    justification="Mock Final Review confirmed PoC authenticity and execution output.",
                    attack_vector=vuln.attack_vector,
                )
                vuln.add(
                    phase_id=PHASE_FINAL_REVIEW_ID,
                    phase_name=PHASE_FINAL_REVIEW_NAME,
                    finding=final_review,
                )

        all_vulnerabilities.append(vuln)

    return all_vulnerabilities, "Success"
