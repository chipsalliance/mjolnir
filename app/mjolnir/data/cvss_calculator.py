# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""CVSS v3.1 specification parser and deterministic base score calculator."""

import math
import re
from typing import Optional, Tuple


def _round_up(val: float) -> float:
    """CVSS v3.1 standard round up function: ceiling to 1 decimal place.

    Follows the official FIRST specification:
    'The Round up function returns the smallest number, specified to 1 decimal place,
    that is equal to or higher than its input. For example, Round up (4.02) returns 4.1;
    and Round up (4.00) returns 4.0.'
    """
    int_input = round(val * 100000)
    if int_input % 10000 == 0:
        return int_input / 100000.0
    return (int(int_input / 10000) + 1) / 10.0


def calculate_cvss31_base_score(vector_str: Optional[str]) -> Tuple[Optional[float], str]:
    """Parses a CVSS v3.1 vector string and calculates the deterministic base score.

    Returns:
        (score, normalized_vector): The calculated float base score (0.0 to 10.0)
        and canonical vector string, or (None, "") if invalid or empty.
    """
    if not vector_str:
        return None, ""

    raw = str(vector_str).strip()
    if not raw:
        return None, ""

    # Metric weight dictionaries according to FIRST CVSS v3.1 Specification
    av_weights = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
    ac_weights = {"L": 0.77, "H": 0.44}
    pr_weights_unchanged = {"N": 0.85, "L": 0.62, "H": 0.27}
    pr_weights_changed = {"N": 0.85, "L": 0.68, "H": 0.50}
    ui_weights = {"N": 0.85, "R": 0.62}
    cia_weights = {"N": 0.0, "L": 0.22, "H": 0.56}

    # Extract components
    parts = raw.split("/")
    metrics = {}
    for part in parts:
        if ":" in part:
            k, v = part.split(":", 1)
            metrics[k.strip().upper()] = v.strip().upper()

    # Validate mandatory metrics: AV, AC, PR, UI, S, C, I, A
    required_keys = ["AV", "AC", "PR", "UI", "S", "C", "I", "A"]
    if not all(k in metrics for k in required_keys):
        return None, raw

    av = metrics["AV"]
    ac = metrics["AC"]
    pr = metrics["PR"]
    ui = metrics["UI"]
    scope = metrics["S"]
    c = metrics["C"]
    i = metrics["I"]
    a = metrics["A"]

    if (
        av not in av_weights
        or ac not in ac_weights
        or ui not in ui_weights
        or scope not in ("U", "C")
        or c not in cia_weights
        or i not in cia_weights
        or a not in cia_weights
    ):
        return None, raw

    scope_changed = scope == "C"
    if scope_changed:
        if pr not in pr_weights_changed:
            return None, raw
        pr_weight = pr_weights_changed[pr]
    else:
        if pr not in pr_weights_unchanged:
            return None, raw
        pr_weight = pr_weights_unchanged[pr]

    # ISS (Impact Sub-Score)
    iss = 1.0 - ((1.0 - cia_weights[c]) * (1.0 - cia_weights[i]) * (1.0 - cia_weights[a]))
    if iss <= 0.0:
        return 0.0, f"CVSS:3.1/AV:{av}/AC:{ac}/PR:{pr}/UI:{ui}/S:{scope}/C:{c}/I:{i}/A:{a}"

    # Impact
    if not scope_changed:
        impact = 6.42 * iss
    else:
        impact = 7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15)

    # Exploitability
    exploitability = 8.22 * av_weights[av] * ac_weights[ac] * pr_weight * ui_weights[ui]

    # Base Score
    if impact <= 0.0:
        base_score = 0.0
    elif not scope_changed:
        base_score = min(10.0, _round_up(min(impact + exploitability, 10.0)))
    else:
        base_score = min(10.0, _round_up(min(1.08 * (impact + exploitability), 10.0)))

    # Ensure 1 decimal place precision
    score_rounded = round(base_score, 1)
    canonical_vector = f"CVSS:3.1/AV:{av}/AC:{ac}/PR:{pr}/UI:{ui}/S:{scope}/C:{c}/I:{i}/A:{a}"
    return score_rounded, canonical_vector
