# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from enum import Enum

class Severity(str, Enum):
    INFORMATIONAL = "Informational"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"
    SKIPPED = "Skipped"
