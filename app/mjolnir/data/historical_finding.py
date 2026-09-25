# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from typing import Optional
from pydantic import BaseModel, Field
from data.severity import Severity
from data.verdict import Verdict
from data.status import Status


class HistoricalFinding(BaseModel):
    phase_id: str
    phase_name: str
    status: Status = Status.OPEN

    title: str
    severity: Severity
    location: str
    description: str
    recommendation: str
    verdict: Optional[Verdict] = None
    justification: Optional[str] = None
    attack_vector: Optional[str] = None
    cwe: Optional[str] = None
    attack_boundary: Optional[str] = None
    demonstrated_impact: Optional[str] = None
    cvss_score: Optional[float] = None
    cvss_vector: Optional[str] = None
    security_objective_violation: Optional[str] = None
    poc: Optional[str] = None
    poc_verified: Optional[bool] = None
    test_command: Optional[str] = None
    duplicate_of: Optional[str] = None
