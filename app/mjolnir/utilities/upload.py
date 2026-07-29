# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import os
import sys
from google.cloud import storage

from utilities.logger import logger
from utilities import dashboard

GCS_VERSION_PREFIX = "v0"


def _upload_to_gcs(bucket_name: str, run_dir: str, destination_prefix: str):
    """Uploads the files in the scan run directory to Google Cloud Storage."""
    logger.info(f"Connecting to GCS Bucket: {bucket_name}.")

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    run_path = Path(run_dir)
    for root, _, files in os.walk(run_dir):
        root_path = Path(root)
        for file in files:
            local_file_path = root_path / file
            # Resolve path relative to target run directory
            rel_path = str(local_file_path.relative_to(run_path))
            blob_name = f"{destination_prefix}/{rel_path}"

            logger.debug(f"Uploading {rel_path} -> gs://{bucket_name}/{blob_name}")

            blob = bucket.blob(blob_name)
            blob.upload_from_filename(local_file_path)


def upload_run_to_gcs(run_dir: str, repo_name: str, job_name: str, run_id_dir: str):
    """Checks for storage configs and triggers the GCS bucket uploads."""
    gcs_bucket = os.environ.get("CLOUD_STORAGE_BUCKET")

    if not gcs_bucket:
        logger.error(
            "GCS upload required but CLOUD_STORAGE_BUCKET environment variable is not set."
        )
        sys.exit(1)

    destination_prefix = (
        f"{GCS_VERSION_PREFIX}/runs/{repo_name}/{job_name.replace(' ', '_')}/run_{run_id_dir}"
    )

    try:
        _upload_to_gcs(gcs_bucket, run_dir, destination_prefix)
        logger.success("GCS upload completed successfully.")
    except Exception as e:
        logger.error(f"GCS upload failed: {e}.")


def upload_dashboard_to_gcs():
    """Downloads GCS run reports in memory, compiles the dashboard, and uploads it back to GCS."""
    gcs_bucket = os.environ.get("CLOUD_STORAGE_BUCKET")

    if not gcs_bucket:
        logger.error(
            "GCS upload required but CLOUD_STORAGE_BUCKET environment variable is not set."
        )
        sys.exit(1)

    logger.info(f"Generating GCS dashboard.")

    try:
        client = storage.Client()
        bucket = client.bucket(gcs_bucket)
        blobs = bucket.list_blobs(prefix=f"{GCS_VERSION_PREFIX}/runs/")

        # Structure remote runs
        remote_runs = {}
        for blob in blobs:
            # Look for vulnerabilities.json files
            if not blob.name.endswith("vulnerabilities.json"):
                continue

            # Extract path hierarchy: v0/runs/{project}/{job}/run_{run_id}/vulnerabilities.json
            parts = blob.name.split("/")
            if len(parts) < 6:
                continue

            project_name = parts[2]
            job_name = parts[3]
            run_name = parts[4]

            run_key = f"{project_name}-{job_name}-{run_name}"
            remote_runs[run_key] = {
                "project": project_name,
                "job": job_name,
                "run": run_name,
                "report_blob": blob,
                "metadata_blob_name": f"{GCS_VERSION_PREFIX}/runs/{project_name}/{job_name}/{run_name}/metadata.json",
            }

        scan_data = {}
        logger.debug(f"Parsing {len(remote_runs)} remote run reports in memory...")
        for run_key, run_info in remote_runs.items():
            try:
                # 1. Download and parse GCS vulnerabilities.json (contains history)
                full_vulnerabilities = json.loads(run_info["report_blob"].download_as_text())

                # Filter for OPEN findings
                open_findings = [v for v in full_vulnerabilities if v.get("status") == "Open"]
                report_data = {"vulnerabilities": open_findings}

                # 2. Download and parse metadata if present
                metadata = {}
                meta_blob = bucket.blob(run_info["metadata_blob_name"])
                if meta_blob.exists():
                    metadata = json.loads(meta_blob.download_as_text())

                # 3. Format scan data
                scan_data[run_key] = dashboard.format_scan_data(
                    run_info["project"],
                    run_info["job"],
                    run_info["run"],
                    report_data,
                    metadata,
                    full_vulnerabilities,
                )
            except Exception as e:
                logger.warning(f"Failed to parse GCS run {run_key}: {e}")

        if not scan_data:
            logger.info("No valid GCS scan reports found. GCS dashboard not compiled.")
            return

        # 4. Compile HTML pages using shared renderer and upload to GCS under v0/web/ (MPA)
        pages = dashboard.render_all_dashboard_pages(scan_data)
        for rel_path, (content, content_type) in pages.items():
            blob_name = f"{GCS_VERSION_PREFIX}/web/{rel_path}"
            bucket.blob(blob_name).upload_from_string(content, content_type=content_type)

        logger.success(f"GCS dashboard uploaded successfully (MPA).")
    except Exception as e:
        logger.error(f"Warning: Failed to generate and upload GCS dashboard: {e}.")
