# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import sys
import argparse
import json
import common


def main():
    parser = argparse.ArgumentParser(
        description="Generate Markdown report from JSON findings."
    )
    parser.add_argument(
        "--input", required=True, help="Path to the findings JSON file."
    )
    parser.add_argument(
        "--output", required=True, help="Path to the output Markdown file."
    )
    args = parser.parse_args()

    try:
        with open(args.input, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        sys.exit(1)

    vulns = data.get("vulnerabilities", [])

    with open(args.output, "w") as f:
        f.write("# Threat Analysis Report\n\n")

        for vuln in vulns:
            file_path = vuln.get("file", "Unknown")
            title = vuln.get("title", "Untitled Vulnerability")
            severity = vuln.get("severity", "Unknown")

            f.write(f"## File: {file_path}\n\n")
            f.write(f"### {title}\n")
            f.write(f"**Severity:** {severity}\n\n")

            # Write all other fields dynamically from the Pydantic Finding model definition
            multiline_fields = {
                "description",
                "recommendation",
                "justification",
                "attack_vector",
            }
            for name, field in common.Finding.model_fields.items():
                if name in ["file", "title", "severity"]:
                    continue

                val = vuln.get(name)
                if not val:
                    continue

                multiline = name in multiline_fields
                display_name = name.replace("_", " ").title()

                if multiline:
                    f.write(f"#### {display_name}\n{val}\n\n")
                else:
                    f.write(f"**{display_name}:** {val}\n\n")

            f.write("---\n\n")

    print(f"Markdown report generated successfully: {args.output}")


if __name__ == "__main__":
    main()
