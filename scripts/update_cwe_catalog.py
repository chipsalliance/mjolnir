#!/usr/bin/env python3
# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Generates the static MITRE CWE catalog JSON bundle for Mjolnir and Nidhogg.

Downloads the official MITRE CWE Research View (CWE-1000) CSV archive and extracts
all recognized CWE IDs, titles, and concise descriptions into app/mjolnir/data/cwe_catalog.json.

Per MITRE's Terms of Use (https://cwe.mitre.org/about/termsofuse.html):
"CWE is free to use by any organization or individual for any research, development,
and/or commercial purposes... The MITRE Corporation hereby grants you a non-exclusive,
royalty-free license to use CWE... on the condition that you reproduce MITRE's copyright
designation and this license in any such copy. CWE is a trademark of The MITRE Corporation."
"""

import csv
import io
import json
from pathlib import Path
import sys
import urllib.request
import zipfile

MITRE_CWE_1000_URL = "https://cwe.mitre.org/data/csv/1000.csv.zip"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "app/mjolnir/data/cwe_catalog.json"


def fetch_cwe_catalog() -> dict:
    print(f"Downloading MITRE CWE catalog from {MITRE_CWE_1000_URL}...")
    req = urllib.request.Request(
        MITRE_CWE_1000_URL,
        headers={"User-Agent": "Mjolnir-CWE-Ingest/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        zip_bytes = resp.read()

    catalog = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for fname in zf.namelist():
            if not fname.endswith(".csv"):
                continue
            print(f"Parsing {fname}...")
            content = zf.read(fname).decode("utf-8", errors="replace")
            reader = csv.reader(content.splitlines())
            header = None
            for row in reader:
                if not row:
                    continue
                if "CWE-ID" in row:
                    header = row
                    continue
                if header and len(row) >= 2:
                    cwe_num = row[0].strip()
                    cwe_name = row[1].strip()
                    if cwe_num.isdigit():
                        cwe_id = f"CWE-{cwe_num}"
                        desc = row[4].strip() if len(row) > 4 else ""
                        catalog[cwe_id] = {
                            "id": cwe_id,
                            "name": cwe_name,
                            "description": desc,
                        }

    return catalog


def main() -> None:
    catalog = fetch_cwe_catalog()
    if not catalog:
        print("Error: No CWE records parsed from MITRE zip.", file=sys.stderr)
        sys.exit(1)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "license_notice": (
            "CWE is a trademark of The MITRE Corporation. Used under the MITRE CWE Terms of Use "
            "(https://cwe.mitre.org/about/termsofuse.html). Copyright (c) The MITRE Corporation."
        ),
        "total_cwes": len(catalog),
        "cwes": catalog,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)

    print(f"Successfully generated {OUTPUT_FILE} with {len(catalog)} CWE entries.")


if __name__ == "__main__":
    main()
