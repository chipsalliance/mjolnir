#!/usr/bin/env python3
# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

import argparse
import mimetypes
import sys
from pathlib import Path

from google.cloud import storage

from mjolnir.constants import WEB_SUBDIR


def deploy_web(web_dir: Path, client: storage.Client, bucket_name: str):
    print(f"Deploying WASM Web Dashboard static assets to gs://{bucket_name}/...")
    bucket = client.bucket(bucket_name)

    dist_dir = web_dir / "dist"
    if not dist_dir.exists():
        print(f"Error: {dist_dir} directory does not exist. Run 'cargo xtask web' first.")
        sys.exit(1)

    source_files = [
        web_dir / "index.html",
        web_dir / "style.css",
        web_dir / "app.js",
        web_dir / "constants.js",
        web_dir / "wasm-worker.js",
    ] + [p for p in sorted(dist_dir.iterdir()) if p.is_file() and not p.name.endswith(".d.ts")]

    for local_file in source_files:
        if not local_file.is_file():
            print(f"Warning: File {local_file} not found, skipping.")
            continue

        rel_path = local_file.relative_to(web_dir)
        target_blob_path = (
            "index.html" if rel_path == Path("index.html") else f"{WEB_SUBDIR}/{rel_path}"
        )

        match local_file.suffix:
            case ".wasm":
                mime = "application/wasm"
            case ".js":
                mime = "application/javascript"
            case ".css":
                mime = "text/css; charset=utf-8"
            case ".html" | ".htm":
                mime = "text/html; charset=utf-8"
            case _:
                mime, _ = mimetypes.guess_type(str(local_file))
                if not mime:
                    mime = "application/octet-stream"

        blob = bucket.blob(target_blob_path)
        blob.cache_control = "no-cache, no-store, must-revalidate"
        blob.upload_from_filename(str(local_file), content_type=mime)
        print(f"  Uploaded {rel_path} -> gs://{bucket_name}/{target_blob_path} ({mime})")

    print(f"Web Dashboard successfully deployed to gs://{bucket_name}/!")


def main():
    parser = argparse.ArgumentParser(description="Mjolnir Web Dashboard GCS Deployment Utility")
    parser.add_argument(
        "--bucket",
        type=str,
        required=True,
        help="Target Google Cloud Storage bucket name",
    )
    parser.add_argument(
        "--web-dir",
        type=str,
        default=str(Path(__file__).resolve().parent.parent / "web"),
        help="Path to web dashboard directory (default: ./web)",
    )
    args = parser.parse_args()

    web_dir = Path(args.web_dir).resolve()
    client = storage.Client()
    deploy_web(web_dir, client, args.bucket)


if __name__ == "__main__":
    main()
