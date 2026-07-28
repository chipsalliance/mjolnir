# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from typing import List
from pydantic import BaseModel, Field
from data.audit_finding import AuditFinding


class SecurityReport(BaseModel):
    vulnerabilities: List[AuditFinding] = Field(
        description="List of detected security vulnerabilities"
    )

    def to_vulnerabilities(self, fallback_file_path: str = "unknown_file") -> List["Vulnerability"]:
        """Converts SecurityReport audit findings to Vulnerability model instances."""
        from data.vulnerability import Vulnerability

        vulns: List[Vulnerability] = []
        for af in self.vulnerabilities:
            target_file = af.file if af.file and af.file != "unknown_file" else fallback_file_path
            vulns.append(Vulnerability.from_audit_finding(af, file_path=target_file))
        return vulns
