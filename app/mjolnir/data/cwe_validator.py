# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""CWE Catalog helper and validator module."""

import functools
import json
from pathlib import Path
import re
from typing import Optional

CWE_CATALOG_FILE = Path(__file__).resolve().parent / "cwe_catalog.json"


@functools.lru_cache(maxsize=1)
def load_cwe_catalog() -> dict[str, dict]:
    """Loads the bundled MITRE CWE catalog into memory."""
    if not CWE_CATALOG_FILE.exists():
        return {}
    try:
        with open(CWE_CATALOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("cwes", {})
    except Exception:
        return {}


def normalize_and_validate_cwe(val: Optional[str]) -> str:
    """Validates that a CWE string references an authentic MITRE CWE identifier.

    Accepts formats such as 'CWE-20', 'cwe-20', or 'CWE-20: Improper Input Validation'.
    If valid, returns the canonical format: 'CWE-<ID>: <Official Title>'.
    If empty or None, returns ''.
    If invalid or hallucinated, raises a ValueError detailing the valid format.
    """
    if not val:
        return ""

    raw = str(val).strip()
    if not raw:
        return ""

    catalog = load_cwe_catalog()
    if not catalog:
        # Fallback if catalog not loaded
        return raw

    # Match ID pattern: CWE-123
    match = re.match(r"^(CWE-\d+)", raw, re.IGNORECASE)
    if not match:
        raise ValueError(
            f"Invalid CWE format: '{raw}'. Expected 'CWE-<NUMBER>' (e.g., 'CWE-20', 'CWE-1256')."
        )

    cwe_id = match.group(1).upper()
    if cwe_id not in catalog:
        raise ValueError(
            f"Unrecognized or hallucinated CWE identifier: '{cwe_id}'. "
            "Must be an official MITRE CWE ID from the CWE-1000 catalog."
        )

    canonical_name = catalog[cwe_id].get("name", "Unknown Weakness")
    return f"{cwe_id}: {canonical_name}"


def search_cwe_catalog(query: str, limit: int = 5) -> list[dict]:
    """Performs a lightweight keyword search against the bundled MITRE CWE catalog.

    Returns a list of dicts with 'id', 'name', and 'description'.
    """
    catalog = load_cwe_catalog()
    if not catalog or not query:
        return []

    tokens = [t.lower() for t in query.split() if len(t) > 1]
    if not tokens:
        return []

    scored_entries = []
    for cwe_id, data in catalog.items():
        name = data.get("name", "").lower()
        desc = data.get("description", "").lower()

        score = 0
        for t in tokens:
            if t in cwe_id.lower():
                score += 10
            if t in name:
                score += 5
            if t in desc:
                score += 1

        if score > 0:
            scored_entries.append((score, data))

    scored_entries.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored_entries[:limit]]
