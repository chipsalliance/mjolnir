# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import argparse
import re
import common


def extract_sloppy_toml_blocks(text):
    """
    Extracts TOML output from RAW agent output.
    Ignores preambles, postambles, and gracefully handles unescaped quotes.
    """
    # Split the text by the TOML array header
    blocks = re.split(r"\[\[vulnerabilit(?:ies|y)\]\]", text, flags=re.IGNORECASE)

    parsed_vulns = []

    for block in blocks:
        vuln = {}
        for key in common.KNOWN_KEYS:
            # Try to match triple-quoted multi-line strings first
            triple_match = re.search(
                rf'^{key}\s*=\s*"""(.*?)"""', block, re.MULTILINE | re.DOTALL
            )
            if triple_match:
                vuln[key] = triple_match.group(1).strip()
                continue

            # Try to match single-quoted lines.
            # The (.*) absorbs unescaped inner quotes
            single_match = re.search(rf'^{key}\s*=\s*"(.*)"\s*$', block, re.MULTILINE)
            if single_match:
                vuln[key] = single_match.group(1).strip()

        if vuln.get("title") and vuln.get("file"):
            parsed_vulns.append(vuln)

    return parsed_vulns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True, help="Original main_report.toml")
    parser.add_argument("--review", required=True, help="Raw text output from agent")
    parser.add_argument("--output", required=True, help="Path for reviewed_report.toml")
    args = parser.parse_args()

    # Load Original TOML
    with open(args.original, "r") as f:
        original_text = f.read()

    original_vulns = extract_sloppy_toml_blocks(original_text)

    if not original_vulns:
        print("WARNING: Original report contained no valid vulnerabilities.")
        original_vulns = [
            {
                common.KEY_FILE: "Pipeline",
                common.KEY_TITLE: "Initial Audit Failed",
                common.KEY_SEVERITY: "Informational",
                common.KEY_DESC: "The initial security auditor produced unparsable output.",
                common.KEY_REC: "Check the raw execution logs.",
            }
        ]

    # Read Raw Output
    try:
        with open(args.review, "r") as f:
            review_text = f.read()
    except Exception:
        review_text = ""

    # Extract the reviewed vulnerabilities using the same parser
    reviewed_vulns_list = extract_sloppy_toml_blocks(review_text)

    # Map them by file::title for easy merging
    reviews_map = {f"{v.get('file')}::{v.get('title')}": v for v in reviewed_vulns_list}

    # Merge Data & Apply Defaults
    for vuln in original_vulns:
        key = f"{vuln.get('file')}::{vuln.get('title')}"

        # Set our required baseline fallbacks
        if "verdict" not in vuln:
            vuln["verdict"] = "Informational"
        if "justification" not in vuln:
            vuln["justification"] = "Not explicitly reviewed by AI or failed to parse."

        # If the agent analyzed it, overwrite with their keys
        if key in reviews_map:
            rev = reviews_map[key]
            for k in ["verdict", "severity", "justification", "attack_vector"]:
                if rev.get(k):
                    vuln[k] = rev[k]

    # Write out the final TOML
    with open(args.output, "w") as f:
        for vuln in original_vulns:
            f.write("[[vulnerabilities]]\n")
            for k, v in vuln.items():
                if not v:
                    continue

                # Safely escape multi-line or long text into triple quotes
                if "\n" in str(v) or k in [
                    "description",
                    "justification",
                    "attack_vector",
                    "recommendation",
                ]:
                    safe_v = str(v).replace('"""', "'''")
                    f.write(f'{k} = """\n{safe_v}\n"""\n')
                else:
                    safe_v = str(v).replace('"', '\\"')
                    f.write(f'{k} = "{safe_v}"\n')
            f.write("\n")


if __name__ == "__main__":
    main()
