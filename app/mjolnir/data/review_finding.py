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
    attack_vector: str = Field(default="", description="Description of the attack vector.")
    refusal_reason: Optional[str] = Field(
        default=None,
        description=(
            "If internal safety guardrails or policy constraints prevent you from "
            "reviewing this finding, state the exact reason here."
        ),
    )
