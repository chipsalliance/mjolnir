# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Audit finding data model."""

from pydantic import BaseModel, Field
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
    file: str | None = Field(
        default="unknown_file",
        description="Relative file path of the source code being analyzed.",
    )
