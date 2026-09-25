# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Deduplication finding models and report schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field
from data.status import Status


class DeduplicationDecision(BaseModel):
    """Decision indicating whether a current finding is a duplicate of a canonical finding."""

    finding_id: str = Field(
        description="ID of the current-run finding being evaluated.",
    )
    status: Status = Field(
        description="Assigned status: 'Duplicate' if this finding duplicates another, or 'Open' if it is uniquely valid.",
    )
    duplicate_of: Optional[str] = Field(
        default=None,
        description=(
            "If status is 'Duplicate', specify the canonical finding ID or reference it duplicates "
            "(either an intra-run finding ID from current findings, or an historical ref like 'job/run/vuln_id'). "
            "If status is 'Open', leave None."
        ),
    )
    justification: str = Field(
        description="Brief technical explanation of why this finding duplicates the canonical finding (or why it is unique).",
    )


class DeduplicationReport(BaseModel):
    """Overall report produced by DeduplicationAgent."""

    decisions: List[DeduplicationDecision] = Field(
        default_factory=list,
        description="Deduplication decision for each candidate Open finding in the current run.",
    )
    refusal_reason: Optional[str] = Field(
        default=None,
        description="If safety constraints prevent reviewing deduplication, state reason here.",
    )


class DeduplicationFinding(BaseModel):
    """Data model passed to Vulnerability.add() during the deduplication phase."""

    status: Status = Field(
        default=Status.OPEN,
        description="Updated vulnerability status.",
    )
    duplicate_of: Optional[str] = Field(
        default=None,
        description="Canonical reference if this finding is a duplicate.",
    )
    justification: str = Field(
        default="Kept as unique Open finding.",
        description="Justification for the deduplication decision.",
    )
