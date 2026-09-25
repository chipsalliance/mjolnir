# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from typing import Optional
from pydantic import BaseModel, Field
from data.severity import Severity
from data.verdict import Verdict


class ReviewFinding(BaseModel):
    title: str = Field(description="Vulnerability Title (can be modified).")
    severity: Severity = Field(description="Re-assessed severity.")
    location: str = Field(description="Line number or function name.")
    description: str = Field(description="Refined technical description.")
    recommendation: str = Field(description="Refined recommendation.")

    verdict: Verdict = Field(description="Exploitability verdict.")
    justification: str = Field(description="Justification of the verdict.")
    attack_vector: str = Field(
        default="",
        description="Detailed exploit path detailing prerequisites, trigger mechanism, state corruption, and adversary payoff.",
    )

    cvss_score: Optional[float] = Field(
        default=None,
        description="Estimated CVSS v3.1 base score (0.0 to 10.0).",
    )
    cvss_vector: Optional[str] = Field(
        default="",
        description="Estimated CVSS v3.1 vector string (e.g. 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H').",
    )
    security_objective_violation: Optional[str] = Field(
        default="",
        description="Silicon/Root-of-Trust security objective violated (e.g. 'SECURE_BOOT_BYPASS', 'KEY_EXFILTRATION', 'ANTI_ROLLBACK_BYPASS', 'PERSISTENT_DENIAL_OF_SERVICE', 'PRIVILEGE_ESCALATION', 'DEFENSE_IN_DEPTH').",
    )
    refusal_reason: Optional[str] = Field(
        default=None,
        description=(
            "If internal safety guardrails or policy constraints prevent you from "
            "reviewing this finding, state the exact reason here."
        ),
    )
