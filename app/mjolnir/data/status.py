# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from enum import Enum


class Status(str, Enum):
    OPEN = "Open"
    CLOSED = "Closed"
