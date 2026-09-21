# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from typing import List, Optional
from pydantic import BaseModel, Field
from constants import PHASE_DISCOVERY_ID, PHASE_DISCOVERY_NAME
from data.audit_finding import AuditFinding
from data.vulnerability import Vulnerability


class SecurityReport(BaseModel):
    vulnerabilities: List[AuditFinding] = Field(
        default_factory=list,
        description="List of detected security vulnerabilities",
    )
    refusal_reason: Optional[str] = Field(
        default=None,
        description=(
            "If internal safety guardrails or policy constraints prevent you from "
            "evaluating this file, state the exact reason here instead of silently returning "
            "an empty vulnerabilities list."
        ),
    )

    def to_vulnerabilities(
        self,
        fallback_file_path: str = "unknown_file",
        phase_id: str = PHASE_DISCOVERY_ID,
        phase_name: str = PHASE_DISCOVERY_NAME,
    ) -> List[Vulnerability]:
        """Converts SecurityReport audit findings to Vulnerability model instances."""
        vulns: List[Vulnerability] = []
        for af in self.vulnerabilities:
            target_file = af.file if af.file and af.file != "unknown_file" else fallback_file_path
            vulns.append(
                Vulnerability.from_audit_finding(
                    af,
                    file_path=target_file,
                    phase_id=phase_id,
                    phase_name=phase_name,
                )
            )
        return vulns
