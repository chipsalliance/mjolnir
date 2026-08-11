#!/usr/bin/env python3
# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path
from google.cloud import storage


def load_dotenv(workspace_root: Path):
    """Loads environment variables from workspace .env file if present."""
    env_file = workspace_root / ".env"
    if env_file.is_file():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val


def get_bucket_name() -> str:
    bucket = os.environ.get("CLOUD_STORAGE_BUCKET")
    if not bucket:
        print("Error: CLOUD_STORAGE_BUCKET environment variable or .env entry is missing.")
        sys.exit(1)
    return bucket


def deploy_web(workspace_root: Path, client: storage.Client, bucket_name: str):
    print(f"Deploying WASM Web Dashboard static assets to gs://{bucket_name}/...")
    bucket = client.bucket(bucket_name)

    web_dir = workspace_root / "web"
    dist_dir = web_dir / "dist"

    if not dist_dir.exists():
        print("Error: web/dist/ directory does not exist. Run 'cargo xtask web' first.")
        sys.exit(1)

    files_to_upload = [
        ("index.html", "index.html", "text/html; charset=utf-8"),
        ("style.css", "web/style.css", "text/css; charset=utf-8"),
        ("app.js", "web/app.js", "application/javascript"),
        ("wasm-worker.js", "web/wasm-worker.js", "application/javascript"),
        ("dist/build_info.js", "web/dist/build_info.js", "application/javascript"),
        (
            "dist/token_usage_module.js",
            "web/dist/token_usage_module.js",
            "application/javascript",
        ),
        (
            "dist/tool_usage_module.js",
            "web/dist/tool_usage_module.js",
            "application/javascript",
        ),
        (
            "dist/mjolnir_dashboard_wasm.js",
            "web/dist/mjolnir_dashboard_wasm.js",
            "application/javascript",
        ),
        (
            "dist/mjolnir_dashboard_wasm_bg.wasm",
            "web/dist/mjolnir_dashboard_wasm_bg.wasm",
            "application/wasm",
        ),
    ]

    for local_rel_path, target_blob_path, content_type in files_to_upload:
        local_file = web_dir / local_rel_path
        if not local_file.is_file():
            print(f"Warning: File {local_file} not found, skipping.")
            continue

        blob = bucket.blob(target_blob_path)
        blob.cache_control = "no-cache, no-store, must-revalidate"
        blob.upload_from_filename(str(local_file), content_type=content_type)
        print(
            f"  Uploaded {local_rel_path} -> gs://{bucket_name}/{target_blob_path} ({content_type})"
        )

    print(f"Web Dashboard successfully deployed to gs://{bucket_name}/!")


def is_test_project(proj_name: str) -> bool:
    p = proj_name.lower()
    return p == "tests" or p.startswith("test")


def deploy_runs(
    workspace_root: Path,
    client: storage.Client,
    bucket_name: str,
    include_tests: bool = False,
):
    print(
        f"Scanning local runs in output/v1/runs/ for deployment to gs://{bucket_name}/v1/runs/ (Include test runs: {include_tests})..."
    )
    bucket = client.bucket(bucket_name)

    runs_dir = workspace_root / "output" / "v1" / "runs"
    if not runs_dir.exists():
        print(f"No local runs found under {runs_dir}.")
        return

    # List all existing blobs under v1/runs/ to prevent duplicate uploads
    print("Fetching existing runs in GCS bucket...")
    existing_blobs = set(b.name for b in client.list_blobs(bucket, prefix="v1/runs/"))

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

                gcs_run_prefix = f"v1/runs/{proj_name}/{job_name}/{run_id}"

                check_blob_name = f"{gcs_run_prefix}/metadata.json"
                if check_blob_name in existing_blobs:
                    skipped_count += 1
                    continue

                print(f"  Uploading new run: {gcs_run_prefix}...")
                for file_path in run_dir.rglob("*"):
                    if file_path.is_file():
                        rel_file = file_path.relative_to(run_dir)
                        blob_name = f"{gcs_run_prefix}/{rel_file}"
                        mime, _ = mimetypes.guess_type(str(file_path))
                        if not mime:
                            mime = "application/octet-stream"

                        blob = bucket.blob(blob_name)
                        blob.upload_from_filename(str(file_path), content_type=mime)

                uploaded_count += 1
                print(f"  Uploaded {gcs_run_prefix}")

    print(f"\nGCS Runs Deployment Complete: {uploaded_count} uploaded, {skipped_count} skipped.")


def main():
    parser = argparse.ArgumentParser(description="Mjolnir GCS Deployment Utility")
    parser.add_argument("--web", action="store_true", help="Deploy static WASM web dashboard")
    parser.add_argument("--runs", action="store_true", help="Deploy missing local scan runs to GCS")
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test and mock benchmark runs",
    )
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    load_dotenv(workspace_root)
    bucket_name = get_bucket_name()

    client = storage.Client()

    if args.web:
        deploy_web(workspace_root, client, bucket_name)
    elif args.runs:
        deploy_runs(
            workspace_root,
            client,
            bucket_name,
            include_tests=args.include_tests,
        )
    else:
        print("Please specify --web or --runs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
