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
    poc: Optional[str] = None
