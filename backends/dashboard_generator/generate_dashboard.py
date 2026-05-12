# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import sys
import re
import json
import os
import argparse

import tomllib


def generate_html(vulns, metadata, template_path, css_path):
    """Generates the interactive HTML dashboard using template_path."""
    if not os.path.exists(template_path):
        print(f"Error: Template file not found at {template_path}")
        sys.exit(1)

    if not os.path.exists(css_path):
        print(f"Error: CSS file not found at {css_path}")
        sys.exit(1)

    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    with open(css_path, "r", encoding="utf-8") as f:
        css_content = f.read()

    template_content = template_content.replace("{{dashboard_css}}", css_content)

    vulns_json = json.dumps(vulns)
    html = template_content.replace("{{vulns_json}}", vulns_json)

    metadata_json = json.dumps(metadata)
    html = html.replace("{{metadata_json}}", metadata_json)
    return html


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate vulnerability HTML dashboard."
    )
    parser.add_argument(
        "input_file", help="Path to the vulnerability report TOML file."
    )
    parser.add_argument("output_file", help="Path to the output HTML file.")
    parser.add_argument(
        "--template", required=True, help="Path to the HTML template file."
    )
    parser.add_argument(
        "--css", required=True, help="Path to the shared CSS file to inject."
    )

    args = parser.parse_args()

    with open(args.input_file, "r") as f:
        content = f.read().strip()

    # Strip markdown code blocks if present
    if content.startswith("```toml"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    data = tomllib.loads(content)

    vulns_raw = data.get("vulnerabilities", [])
    vulns = []

    for v in vulns_raw:
        file_path = v.get("file", "Unknown")
        parent_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)

        vuln = {
            "file_path": file_path,
            "parent_dir": parent_dir if parent_dir else "/",
            "file_name": file_name,
            "title": v.get("title", "Untitled"),
            "severity": v.get("severity", "Unknown"),
            "description": v.get("description", "")
            + f"\n\n**Location:** {v.get('location', 'N/A')}\n\n**Recommendation:** {v.get('recommendation', 'N/A')}",
        }

        sev = vuln["severity"].lower()
        if "critical" in sev:
            vuln["sev_score"] = 4
            vuln["severity_normalized"] = "Critical"
        elif "high" in sev:
            vuln["sev_score"] = 3
            vuln["severity_normalized"] = "High"
        elif "medium" in sev:
            vuln["sev_score"] = 2
            vuln["severity_normalized"] = "Medium"
        elif "low" in sev:
            vuln["sev_score"] = 1
            vuln["severity_normalized"] = "Low"
        else:
            vuln["sev_score"] = 0
            vuln["severity_normalized"] = "Informational"

        vulns.append(vuln)

    # Load metadata if available
    input_dir = os.path.dirname(args.input_file)
    metadata_file = os.path.join(input_dir, "metadata.toml")
    metadata = {}
    if os.path.exists(metadata_file):
        print(f"Found metadata file at {metadata_file}")
        with open(metadata_file, "rb") as f:
            metadata = tomllib.load(f)

    html = generate_html(vulns, metadata, args.template, args.css)

    with open(args.output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard generated successfully: {args.output_file}")
