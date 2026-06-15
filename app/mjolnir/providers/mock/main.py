# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import json
import uuid
from utilities.logger import logger
from data.vulnerability import Vulnerability
from data.audit_finding import AuditFinding
from data.review_finding import ReviewFinding
from data.severity import Severity
from data.verdict import Verdict
from data.status import Status


def run_analysis(
    model: str,
    code_dir: str,
    files: list,
    threat_model_context: str,
    run_dir: str,
    batch_size: int,
) -> list:
    """Instantly returns hardcoded mock findings and compiles a mock flow history for testing."""

    all_vulnerabilities = []

    from tqdm import tqdm
    pbar = tqdm(files, desc="\tScanning files", unit="file")
    for idx, f_path in enumerate(pbar):
        pbar.set_description(f"\tScanning {f_path} (Mock)")
        ext = os.path.splitext(f_path)[1].lstrip(".").lower()
        prompt_name = "rust_auditor.txt" if ext == "rs" else "c_auditor.txt"

        logger.write(f"Scanning {f_path} (Mock)...", stdout=False)
        logger.write(f"Loaded prompt for .{ext} from: {prompt_name}", stdout=False)

        fid = str(uuid.uuid4())
        
        # 1. Auditor Finding (Phase 1)
        audit_finding = AuditFinding(
            title="Mock Vulnerability",
            severity=Severity.MEDIUM,
            location="Line 42",
            description=f"Mock vulnerability flagged for file '{f_path}' by model '{model}'.",
            recommendation="Replace mock config with production backend."
        )

        vuln = Vulnerability(
            id=fid,
            file=f_path,
            title=audit_finding.title,
            severity=audit_finding.severity,
            location=audit_finding.location,
            description=audit_finding.description,
            recommendation=audit_finding.recommendation
        )
        vuln.add(phase_id="1", phase_name="Source File Exploration", finding=audit_finding)

        # 2. Simulate Reviewer (Phase 2)
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
                attack_vector="Trigger exploit directly."
            )
            vuln.add(phase_id="2", phase_name="Initial Review", finding=review)
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
                attack_vector=""
            )
            vuln.add(phase_id="2", phase_name="Initial Review", finding=review)
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
                attack_vector=""
            )
            vuln.add(phase_id="2", phase_name="Initial Review", finding=review)
        else:
            # Finding is skipped (Omitted by reviewer -> Kept via fail-open)
            vuln.add_skipped(phase_id="2", phase_name="Initial Review", justification="Omitted during mock review simulation.")

        all_vulnerabilities.append(vuln)

    return all_vulnerabilities
