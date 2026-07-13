# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from typing import Optional
from pydantic import BaseModel, Field
from data.severity import Severity


class AuditFinding(BaseModel):
    title: str = Field(description="Vulnerability Title")
    severity: Severity = Field(description="Initial severity assessment.")
    location: str = Field(description="Line number or function name.")
    description: str = Field(description="Detailed technical description.")
    recommendation: str = Field(description="Recommended fix.")
    file: Optional[str] = Field(
        default="unknown_file",
        description="Relative file path of the source code being analyzed.",
    )
