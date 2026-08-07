# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import sys
from pathlib import Path

from google.cloud import storage

from utilities.logger import logger

GCS_VERSION_PREFIX = "v1"


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
