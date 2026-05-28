#!/usr/bin/env python3
"""Aggregates vulnerability scan results from GCS and generates a landing page."""

import argparse
import logging
import os
from pathlib import Path
import subprocess
import sys
import dashboard_builder

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def run_gcloud_storage(args):
    """Runs gcloud storage command and returns output."""
    cmd = ["gcloud", "storage"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"gcloud storage command failed: {e}")
        logging.error(f"stderr: {e.stderr}")
        return None


def find_latest_scan_gcs(bucket, prefix):
    """Finds the latest scan directory in GCS for a given prefix."""
    path = f"gs://{bucket}/{prefix}/"
    output = run_gcloud_storage(["ls", path])
    if not output:
        return None

    lines = output.splitlines()
    # Filter for directories (they end with / in gcloud storage ls output)
    dirs = [line for line in lines if line.endswith("/")]
    if not dirs:
        return None

    # Sort by name (assuming YYYYMMDD_HHMMSS timestamp format at the end)
    dirs.sort()
    return dirs[-1].rstrip("/")


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
        default=str(Path(__file__).resolve().parent / "gcs_components.json"),
        help="Path to components.json file (default: gcs_components.json in script dir).",
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

    components = dashboard_builder.load_components([args.components])

    # Find dashboards dir
    dashboards_dir = (
        Path(args.dashboards_dir)
        if args.dashboards_dir
        else Path(__file__).resolve().parent.parent / "dashboards"
    )

    shared_css, mjolnir_css, html_template = dashboard_builder.get_assets(
        dashboards_dir
    )
    if not html_template:
        sys.exit(1)

    cards_html = ""

    for comp_key, comp_info in components.items():
        display_name = comp_info["display_name"]
        logging.info(f"Processing {display_name}...")

        gcs_prefix = f"{args.prefix}/{comp_key}"
        latest_run = find_latest_scan_gcs(args.bucket, gcs_prefix)

        if not latest_run:
            logging.warning(
                f"No scan data found in GCS for {display_name} at {gcs_prefix}"
            )
            continue

        logging.info(f"Found latest scan: {latest_run}")

        links_html = ""
        files_output = run_gcloud_storage(["ls", latest_run])
        if not files_output:
            continue

        existing_files = [
            os.path.basename(line.rstrip("/")) for line in files_output.splitlines()
        ]

        files_to_link = [
            "dashboard.html",
            "reviewed_report.md",
            "main_report.json",
            "main_report.md",
        ]
        linked_count = 0
        for filename in files_to_link:
            if filename in existing_files:
                parts = latest_run.split(f"gs://{args.bucket}/")
                path_in_bucket = parts[1] if len(parts) > 1 else ""
                url = f"https://storage.googleapis.com/{args.bucket}/{path_in_bucket}/{filename}"

                links_html += dashboard_builder.generate_link_html(filename, url)
                linked_count += 1

        if linked_count > 0:
            cards_html += dashboard_builder.generate_card_html(
                display_name, os.path.basename(latest_run), links_html
            )
        else:
            logging.warning(f"No supported report files found in {latest_run}")

    if cards_html:
        index_html_content = dashboard_builder.build_dashboard(
            html_template, shared_css, mjolnir_css, cards_html
        )

        with open(args.output, "w") as f:
            f.write(index_html_content)
        logging.info(f"Generated landing page at: {args.output}")
        if args.upload:
            logging.info(f"Uploading {args.output} to gs://{args.bucket}/")
            run_gcloud_storage(["cp", args.output, f"gs://{args.bucket}/"])
            url = f"https://storage.googleapis.com/{args.bucket}/{args.output}"
            logging.info(f"Public URL: {url}")
    else:
        logging.error("No results aggregated, index.html not generated.")


if __name__ == "__main__":
    main()
