# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from enum import Enum
from typing import Optional, Union


class Severity(str, Enum):
    INFORMATIONAL = "Informational"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"
    SKIPPED = "Skipped"

    @property
    def rank(self) -> int:
        return {
            Severity.SKIPPED: -1,
            Severity.INFORMATIONAL: 0,
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 3,
            Severity.CRITICAL: 4,
        }[self]

    def meets_threshold(self, min_severity: Optional[Union["Severity", str]]) -> bool:
        """Returns True if this severity is >= min_severity. Returns False if threshold is 'None'/'Off'."""
        if not min_severity:
            return True
        raw = min_severity.value if isinstance(min_severity, Severity) else str(min_severity)
        if raw.strip().lower() in ("none", "off", "disabled"):
            return False
        try:
            threshold = Severity(raw.strip().capitalize())
        except ValueError:
            threshold = Severity.MEDIUM
        return self.rank >= threshold.rank
