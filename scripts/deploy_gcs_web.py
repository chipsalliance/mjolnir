#!/usr/bin/env python3
# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import argparse
import sys
from pathlib import Path
from google.cloud import storage


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


def main():
    parser = argparse.ArgumentParser(description="Mjolnir Web Dashboard GCS Deployment Utility")
    parser.add_argument(
        "--bucket",
        "-b",
        type=str,
        required=True,
        help="Target Google Cloud Storage bucket name",
    )
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    client = storage.Client()
    deploy_web(workspace_root, client, args.bucket)


if __name__ == "__main__":
    main()
