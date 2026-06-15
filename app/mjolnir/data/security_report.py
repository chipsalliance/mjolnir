# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from typing import List
from pydantic import BaseModel, Field
from data.audit_finding import AuditFinding


class SecurityReport(BaseModel):
    vulnerabilities: List[AuditFinding] = Field(
        description="List of detected security vulnerabilities"
    )
