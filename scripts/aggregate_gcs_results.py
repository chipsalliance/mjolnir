#!/usr/bin/env python3
"""Aggregates vulnerability scan results from GCS and generates a landing page."""

import argparse
import logging
import os
from pathlib import Path
import subprocess
import sys
import tomllib

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

FILENAME_MAPPINGS = {
    "dashboard.html": ("Interactive Dashboard", "bg-html", "HTML"),
    "main_report.md": ("Main Vulnerability Report", "bg-md", "MD"),
    "main_report.toml": ("Main Vulnerability Report", "bg-toml", "TOML"),
    "reviewed_report.md": (
        "Agent Filtered Vulnerability Report",
        "bg-md",
        "MD",
    ),
}


def load_components(config_paths):
    """Loads and merges components from multiple TOML files."""
    components = {}
    for path_str in config_paths:
        path = Path(path_str)
        if not path.exists():
            logging.error(f"Components config file not found: {path}")
            sys.exit(1)
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
                components.update(data)
        except Exception as e:
            logging.error(f"Failed to parse components file {path}: {e}")
            sys.exit(1)
    return components


def run_gsutil(args):
    """Runs gsutil command and returns output."""
    cmd = ["gsutil"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"gsutil command failed: {e}")
        logging.error(f"stderr: {e.stderr}")
        return None


def find_latest_scan_gcs(bucket, prefix):
    """Finds the latest scan directory in GCS for a given prefix."""
    path = f"gs://{bucket}/{prefix}/"
    output = run_gsutil(["ls", path])
    if not output:
        return None

    lines = output.splitlines()
    # Filter for directories (they end with / in gsutil ls output)
    dirs = [line for line in lines if line.endswith("/")]
    if not dirs:
        return None

    # Sort by name (assuming YYYYMMDD_HHMMSS timestamp format at the end)
    dirs.sort()
    return dirs[-1].rstrip("/")


def generate_link_html(bucket, comp_key, run_dir_name, filename):
    """Generates HTML link for a report file in GCS."""
    # Assuming public access URL structure
    # https://storage.googleapis.com/[bucket]/[path_in_bucket]/[filename]
    parts = run_dir_name.split(f"gs://{bucket}/")
    if len(parts) < 2:
        return ""
    path_in_bucket = parts[1]

    url = f"https://storage.googleapis.com/{bucket}/{path_in_bucket}/{filename}"

    mapping = FILENAME_MAPPINGS.get(filename)
    if mapping:
        link_text, badge_class, badge_text = mapping
        badge_html = f'<span class="badge {badge_class}">{badge_text}</span>'
    else:
        link_text = filename
        badge_html = ""

    return f'<a href="{url}" class="list-group-item">{link_text}{badge_html}</a>\n'


CARD_TEMPLATE = """
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">{display_name}</h5>
                    <div class="scan-info">📂 <code>{scan_dir}</code></div>
                    <div class="list-group">
                        {links_html}
                    </div>
                </div>
            </div>
"""


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate vulnerability scan results from GCS."
    )
    parser.add_argument("--bucket", required=True, help="GCS bucket name.")
    parser.add_argument(
        "--prefix", default="v0", help="Prefix in the bucket (default: v0)."
    )
    parser.add_argument(
        "--components",
        default=str(Path(__file__).resolve().parent / "gcs_components.toml"),
        help="Path to components.toml file (default: gcs_components.toml in script dir).",
    )
    parser.add_argument("--output", default="index.html", help="Output HTML file path.")
    parser.add_argument(
        "--dashboards-dir",
        help="Path to the dashboards directory containing templates and CSS assets.",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload generated index.html to GCS bucket.",
    )
    args = parser.parse_args()

    components = load_components([args.components])

    # Find dashboards dir
    dashboards_dir = (
        Path(args.dashboards_dir)
        if args.dashboards_dir
        else Path(__file__).resolve().parent.parent / "dashboards"
    )

    shared_css_path = dashboards_dir / "dashboard.css"
    mjolnir_css_path = dashboards_dir / "mjolnir_dashboard.css"
    template_path = dashboards_dir / "mjolnir_dashboard.html.tpl"

    # Read assets
    if not template_path.exists():
        logging.error(f"Template not found: {template_path}")
        sys.exit(1)

    with open(shared_css_path, "r") as f:
        shared_css = f.read()
    with open(mjolnir_css_path, "r") as f:
        mjolnir_css = f.read()
    with open(template_path, "r") as f:
        html_template = f.read()

    cards_html = ""

    for comp_key, comp_info in components.items():
        display_name = comp_info["display_name"]
        logging.info(f"Processing {display_name}...")

        # Assume path in bucket is prefix / comp_key
        gcs_prefix = f"{args.prefix}/{comp_key}"
        latest_run = find_latest_scan_gcs(args.bucket, gcs_prefix)

        if not latest_run:
            logging.warning(
                f"No scan data found in GCS for {display_name} at {gcs_prefix}"
            )
            continue

        logging.info(f"Found latest scan: {latest_run}")

        links_html = ""
        # Check which files exist in that latest run
        files_output = run_gsutil(["ls", latest_run])
        if not files_output:
            continue

        existing_files = [
            os.path.basename(line.rstrip("/")) for line in files_output.splitlines()
        ]

        files_to_link = [
            "dashboard.html",
            "reviewed_report.md",
            "main_report.toml",
            "main_report.md",
        ]
        linked_count = 0
        for filename in files_to_link:
            if filename in existing_files:
                links_html += generate_link_html(
                    args.bucket, comp_key, latest_run, filename
                )
                linked_count += 1

        if linked_count > 0:
            cards_html += CARD_TEMPLATE.format(
                display_name=display_name,
                scan_dir=os.path.basename(latest_run),
                links_html=links_html,
            )
        else:
            logging.warning(f"No supported report files found in {latest_run}")

    if cards_html:
        index_html_content = html_template.replace("{{dashboard_css}}", shared_css)
        index_html_content = index_html_content.replace("{{mjolnir_css}}", mjolnir_css)
        index_html_content = index_html_content.replace("{{cards_html}}", cards_html)

        with open(args.output, "w") as f:
            f.write(index_html_content)
        logging.info(f"Generated landing page at: {args.output}")
        if args.upload:
            logging.info(f"Uploading {args.output} to gs://{args.bucket}/")
            run_gsutil(["cp", args.output, f"gs://{args.bucket}/"])
            url = f"https://storage.googleapis.com/{args.bucket}/{args.output}"
            logging.info(f"Public URL: {url}")
    else:
        logging.error("No results aggregated, index.html not generated.")


if __name__ == "__main__":
    main()
