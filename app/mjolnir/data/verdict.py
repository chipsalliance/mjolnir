# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from enum import Enum


class Verdict(str, Enum):
    EXPLOITABLE = "Exploitable"
    NOT_EXPLOITABLE = "Not Exploitable"
    FALSE_POSITIVE = "False Positive"
