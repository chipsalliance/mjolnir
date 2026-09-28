# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Audit finding data model."""

from pydantic import BaseModel, Field, field_validator
from data.severity import Severity


class AuditFinding(BaseModel):
    """Represents a vulnerability finding emitted during security auditing or report ingestion.

    Note: `file` is optional (defaults to None or 'unknown_file') to support external vulnerability
    reports that describe global or component-level findings without specific source file paths.
    """

    title: str = Field(description="Vulnerability Title")
    severity: Severity = Field(description="Initial severity assessment.")
    location: str = Field(description="Line number or function name.")
    description: str = Field(description="Detailed technical description.")
    recommendation: str = Field(description="Recommended fix.")
    cwe: str = Field(
        default="",
        description=(
            "Standard MITRE CWE ID and title (e.g., 'CWE-20: Improper Input Validation', "
            "'CWE-190: Integer Overflow', 'CWE-1256: Improper Restriction of Software Interfaces "
            "to Hardware Features'). Use the search_cwe tool to verify the authentic MITRE CWE ID."
        ),
    )
    file: str | None = Field(
        default="unknown_file",
        description="Relative file path of the source code being analyzed.",
    )

    @field_validator("cwe", mode="before")
    @classmethod
    def validate_cwe_identifier(cls, v: str) -> str:
        from data.cwe_validator import normalize_and_validate_cwe

        return normalize_and_validate_cwe(v)
