#!/usr/bin/env python3
# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import argparse
import mimetypes
import sys
from pathlib import Path

from google.cloud import storage

from mjolnir.constants import RUNS_SUBDIR


def is_test_project(proj_name: str) -> bool:
    p = proj_name.lower()
    return p == "tests" or p.startswith("test")


def upload_single_run(
    bucket, run_dir: Path, proj_name: str, job_name: str, run_id: str, existing_blobs: set
) -> bool:
    meta_file = run_dir / "metadata.json"
    if not meta_file.is_file():
        print(f"  Skipping incomplete run (missing metadata.json): {run_dir}")
        return False

    gcs_run_prefix = f"{RUNS_SUBDIR}/{proj_name}/{job_name}/{run_id}"
    check_blob_name = f"{gcs_run_prefix}/metadata.json"

    if check_blob_name in existing_blobs:
        return False

    print(f"  Uploading new run: {gcs_run_prefix}...")
    for file_path in sorted(run_dir.rglob("*")):
        if file_path.is_file():
            rel_file = file_path.relative_to(run_dir)
            blob_name = f"{gcs_run_prefix}/{rel_file}"
            mime, _ = mimetypes.guess_type(str(file_path))
            if not mime:
                mime = "application/octet-stream"

            blob = bucket.blob(blob_name)
            blob.upload_from_filename(str(file_path), content_type=mime)

    run_url = f"https://storage.googleapis.com/{bucket.name}/index.html#/run/{proj_name}/{job_name}/{run_id}"
    print(f"  Uploaded {gcs_run_prefix}")
    print(f"  Run URL: {run_url}")
    return True


def deploy_runs(
    output_dir: Path,
    client: storage.Client,
    bucket_name: str,
    include_tests: bool = False,
):
    bucket = client.bucket(bucket_name)

    runs_dir = output_dir / RUNS_SUBDIR
    if not runs_dir.exists():
        print(f"No local runs found under {runs_dir}.")
        return

    print(
        f"Scanning local runs in {runs_dir} for deployment to gs://{bucket_name}/{RUNS_SUBDIR}/ (Include test runs: {include_tests})..."
    )

    print("Fetching existing runs in GCS bucket...")
    existing_blobs = set(b.name for b in client.list_blobs(bucket, prefix=f"{RUNS_SUBDIR}/"))

    uploaded_count = 0
    skipped_count = 0

    for proj_dir in sorted(runs_dir.iterdir()):
        if not proj_dir.is_dir():
            continue
        proj_name = proj_dir.name

        if not include_tests and is_test_project(proj_name):
            print(f"  Excluding test project: {proj_name}")
            continue

        for job_dir in sorted(proj_dir.iterdir()):
            if not job_dir.is_dir():
                continue
            job_name = job_dir.name

            for run_dir in sorted(job_dir.iterdir()):
                if not run_dir.is_dir():
                    continue
                run_id = run_dir.name

                if upload_single_run(bucket, run_dir, proj_name, job_name, run_id, existing_blobs):
                    uploaded_count += 1
                else:
                    skipped_count += 1

    print(f"\nGCS Runs Deployment Complete: {uploaded_count} uploaded, {skipped_count} skipped.")


def main():
    parser = argparse.ArgumentParser(description="Mjolnir Scan Runs GCS Sync Utility")
    parser.add_argument(
        "--bucket",
        type=str,
        required=True,
        help="Target Google Cloud Storage bucket name",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Root output directory containing v1/runs (e.g. ./mjolnir/results)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test and mock benchmark runs",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()

    client = storage.Client()

    deploy_runs(
        output_dir,
        client,
        args.bucket,
        include_tests=args.include_tests,
    )


if __name__ == "__main__":
    main()
