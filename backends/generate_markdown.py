# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import sys
import argparse
import tomllib


def main():
    parser = argparse.ArgumentParser(
        description="Generate Markdown report from TOML findings."
    )
    parser.add_argument(
        "--input", required=True, help="Path to the findings TOML file."
    )
    parser.add_argument(
        "--output", required=True, help="Path to the output Markdown file."
    )
    args = parser.parse_args()

    try:
        with open(args.input, "r") as f:
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
    except Exception as e:
        print(f"Error loading TOML file: {e}")
        sys.exit(1)

    vulns = data.get("vulnerabilities", [])

    with open(args.output, "w") as f:
        f.write("# Threat Analysis Report\n\n")

        for vuln in vulns:
            file_path = vuln.get("file", "Unknown")
            title = vuln.get("title", "Untitled Vulnerability")
            severity = vuln.get("severity", "Unknown")
            location = vuln.get("location", "Unknown")
            description = vuln.get("description", "No description provided.")
            recommendation = vuln.get("recommendation", "No recommendation provided.")

            f.write(f"## File: {file_path}\n\n")
            f.write(f"### {title}\n")
            f.write(f"**Severity:** {severity}\n")
            f.write(f"**Location:** {location}\n\n")
            f.write(f"#### Description\n{description}\n\n")
            f.write(f"#### Recommendation\n{recommendation}\n\n")
            f.write("---\n\n")

    print(f"Markdown report generated successfully: {args.output}")


if __name__ == "__main__":
    main()
