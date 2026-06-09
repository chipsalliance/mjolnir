# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import argparse
import common
import json
from pydantic_core import PydanticUndefined


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True, help="Original main_report.json")
    parser.add_argument(
        "--review", required=True, help="Raw JSON text output from agent"
    )
    parser.add_argument("--output", required=True, help="Path for reviewed_report.json")
    args = parser.parse_args()

    # Load Original JSON
    try:
        with open(args.original, "r") as f:
            data = json.load(f)
            original_vulns = data.get("vulnerabilities", [])
    except Exception as e:
        print(f"Error loading original JSON: {e}")
        original_vulns = []

    if not original_vulns:
        print("WARNING: Original report contained no valid vulnerabilities.")
        original_vulns = [
            common.Finding(
                file="Pipeline",
                title="Initial Audit Failed",
                severity="Informational",
                description="The initial security auditor produced unparsable output.",
                recommendation="Check the raw execution logs.",
            ).model_dump()
        ]

    # Read Raw Output
    try:
        with open(args.review, "r") as f:
            review_text = f.read().strip()
            # Strip markdown fences if LLM wrapped its JSON
            if review_text.startswith("```json"):
                review_text = review_text[7:]
            elif review_text.startswith("```"):
                review_text = review_text[3:]
            if review_text.endswith("```"):
                review_text = review_text[:-3]

            review_data = json.loads(review_text.strip())
            reviewed_vulns_list = review_data.get("vulnerabilities", [])
    except Exception as e:
        print(f"Error parsing reviewed JSON: {e}")
        reviewed_vulns_list = []

    # Map them by file::title for easy merging
    reviews_map = {f"{v.get('file')}::{v.get('title')}": v for v in reviewed_vulns_list}

    # Merge Data & Apply Defaults
    final_vulns = []
    for vuln in original_vulns:
        key = f"{vuln.get('file')}::{vuln.get('title')}"

        # Set baseline fallbacks dynamically from Pydantic model fields
        for name, field in common.Finding.model_fields.items():
            if name not in vuln:
                default_val = field.default
                if default_val is None or default_val is PydanticUndefined:
                    default_val = "Unknown" if name == "file" else ""
                vuln[name] = default_val

        # Try exact match first
        rev = reviews_map.get(key)

        # Fallback: Minimal fuzzy match if LLM changed the title slightly
        if not rev:
            for r_vuln in reviewed_vulns_list:
                if vuln.get("file", "") == r_vuln.get("file", ""):
                    t1 = set(vuln.get("title", "").lower().split())
                    t2 = set(r_vuln.get("title", "").lower().split())
                    if len(t1.intersection(t2)) >= 2 or len(t1) < 2:
                        rev = r_vuln
                        break

        # If the agent analyzed it, overwrite with their keys
        if rev:
            for k in common.Finding.model_fields.keys():
                if k not in ["file", "title"] and rev.get(k):
                    vuln[k] = rev[k]

        # Deletion logic: Skip adding false positives to the final list
        verdict_str = str(vuln.get("verdict", "")).lower()
        severity_str = str(vuln.get("severity", "")).lower()
        if "false positive" in verdict_str or "false positive" in severity_str:
            continue

        final_vulns.append(vuln)

    # Write out the final JSON
    final_report = {"vulnerabilities": final_vulns}
    with open(args.output, "w") as f:
        json.dump(final_report, f, indent=2)


if __name__ == "__main__":
    main()
