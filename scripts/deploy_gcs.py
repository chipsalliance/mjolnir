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
        ("index.html", "text/html; charset=utf-8"),
        ("style.css", "text/css; charset=utf-8"),
        ("app.js", "application/javascript"),
        ("wasm-worker.js", "application/javascript"),
        ("dist/usage_module.js", "application/javascript"),
        ("dist/mjolnir_dashboard_wasm.js", "application/javascript"),
        ("dist/mjolnir_dashboard_wasm_bg.wasm", "application/wasm"),
    ]

    for rel_path, content_type in files_to_upload:
        local_file = web_dir / rel_path
        if not local_file.is_file():
            print(f"Warning: File {local_file} not found, skipping.")
            continue

        blob = bucket.blob(rel_path)
        blob.upload_from_filename(str(local_file), content_type=content_type)
        print(f"  Uploaded {rel_path} -> gs://{bucket_name}/{rel_path} ({content_type})")

    print(f"Web Dashboard successfully deployed to gs://{bucket_name}/!")


def deploy_runs(
    workspace_root: Path, client: storage.Client, bucket_name: str, include_usage: bool = False
):
    print(
        f"Scanning local runs in output/v1/runs/ for deployment to gs://{bucket_name}/v1/runs/ (Include usage telemetry: {include_usage})..."
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

    runs_index = []
    usage_runs = []
    usage_models = {}
    total_input = 0
    total_output = 0
    total_tokens = 0

    for proj_dir in sorted(runs_dir.iterdir()):
        if not proj_dir.is_dir():
            continue
        proj_name = proj_dir.name

        for job_dir in sorted(proj_dir.iterdir()):
            if not job_dir.is_dir():
                continue
            job_name = job_dir.name

            for run_dir in sorted(job_dir.iterdir()):
                if not run_dir.is_dir():
                    continue
                run_id = run_dir.name

                gcs_run_prefix = f"v1/runs/{proj_name}/{job_name}/{run_id}"

                vuln_file = run_dir / "vulnerabilities.json"
                if not vuln_file.exists():
                    vuln_file = run_dir / "finding_phase_1.json"

                meta_file = run_dir / "metadata.json"
                usage_file = run_dir / "usage.json"

                vulns = []
                critical_count = 0
                high_count = 0
                medium_count = 0
                low_count = 0
                open_count = 0
                closed_count = 0

                if vuln_file.exists():
                    try:
                        with open(vuln_file, "r") as f:
                            vulns = json.load(f)
                            if isinstance(vulns, list):
                                for v in vulns:
                                    sev = str(
                                        v.get("severity") or v.get("severity_level") or "LOW"
                                    ).upper()
                                    if sev == "CRITICAL":
                                        critical_count += 1
                                    elif sev == "HIGH":
                                        high_count += 1
                                    elif sev == "MEDIUM":
                                        medium_count += 1
                                    else:
                                        low_count += 1

                                    st = str(v.get("status") or v.get("state") or "Open").lower()
                                    if st in ["closed", "fixed", "resolved"]:
                                        closed_count += 1
                                    else:
                                        open_count += 1
                    except Exception:
                        pass

                meta = {}
                if meta_file.exists():
                    try:
                        with open(meta_file, "r") as f:
                            meta = json.load(f)
                    except Exception:
                        pass

                runs_index.append(
                    {
                        "project": proj_name,
                        "job": job_name,
                        "run_id": run_id,
                        "timestamp": meta.get("timestamp", run_id),
                        "vuln_count": len(vulns) if isinstance(vulns, list) else 0,
                        "critical_count": critical_count,
                        "high_count": high_count,
                        "medium_count": medium_count,
                        "low_count": low_count,
                        "open_count": open_count,
                        "closed_count": closed_count,
                        "vulnerabilities": vulns if isinstance(vulns, list) else [],
                        "model": meta.get("model", "Unknown"),
                        "commit": meta.get("target_commit") or meta.get("commit") or "N/A",
                        "mode": meta.get("mode", "Discovery"),
                        "status": meta.get("status", "Success"),
                        "schema_version": meta.get("schema_version", "v1"),
                    }
                )

                if include_usage and usage_file.exists():
                    try:
                        with open(usage_file, "r") as f:
                            u_data = json.load(f)
                            tot = u_data.get("total", {})
                            inp = tot.get("input_tokens") or tot.get("prompt_tokens") or 0
                            out = tot.get("output_tokens") or tot.get("completion_tokens") or 0
                            tok = tot.get("total_tokens") or 0
                            total_input += inp
                            total_output += out
                            total_tokens += tok

                            model_name = u_data.get("model") or meta.get("model") or "Unknown"
                            if model_name not in usage_models:
                                usage_models[model_name] = {
                                    "model": model_name,
                                    "input_tokens": 0,
                                    "output_tokens": 0,
                                    "total_tokens": 0,
                                    "runs_count": 0,
                                }
                            usage_models[model_name]["input_tokens"] += inp
                            usage_models[model_name]["output_tokens"] += out
                            usage_models[model_name]["total_tokens"] += tok
                            usage_models[model_name]["runs_count"] += 1

                            usage_runs.append(
                                {
                                    "project": proj_name,
                                    "job": job_name,
                                    "run_id": run_id,
                                    "model": model_name,
                                    "total_tokens": tok,
                                    "timestamp": meta.get("timestamp", ""),
                                }
                            )
                    except Exception:
                        pass

                check_blob_name = f"{gcs_run_prefix}/metadata.json"
                if check_blob_name in existing_blobs:
                    if (
                        include_usage
                        and usage_file.exists()
                        and f"{gcs_run_prefix}/usage.json" not in existing_blobs
                    ):
                        blob = bucket.blob(f"{gcs_run_prefix}/usage.json")
                        blob.upload_from_filename(str(usage_file), content_type="application/json")
                    skipped_count += 1
                    continue

                print(f"  Uploading new run: {gcs_run_prefix}...")
                for file_path in run_dir.rglob("*"):
                    if file_path.is_file():
                        if not include_usage and file_path.name == "usage.json":
                            continue
                        rel_file = file_path.relative_to(run_dir)
                        blob_name = f"{gcs_run_prefix}/{rel_file}"
                        mime, _ = mimetypes.guess_type(str(file_path))
                        if not mime:
                            mime = "application/octet-stream"

                        blob = bucket.blob(blob_name)
                        blob.upload_from_filename(str(file_path), content_type=mime)

                uploaded_count += 1
                print(f"  Uploaded {gcs_run_prefix}")

    # Upload static api/runs endpoint for static GCS bucket hosting
    runs_blob = bucket.blob("api/runs")
    runs_blob.upload_from_string(json.dumps(runs_index, indent=2), content_type="application/json")
    print(f"  Uploaded static API endpoint -> gs://{bucket_name}/api/runs")

    if include_usage:
        usage_summary_data = {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_tokens,
            "by_model": list(usage_models.values()),
            "runs": usage_runs,
        }
        usage_blob = bucket.blob("api/usage")
        usage_blob.upload_from_string(
            json.dumps(usage_summary_data, indent=2), content_type="application/json"
        )
        print(f"  Uploaded static API endpoint -> gs://{bucket_name}/api/usage")

    print(f"\nGCS Runs Deployment Complete: {uploaded_count} uploaded, {skipped_count} skipped.")


def main():
    parser = argparse.ArgumentParser(description="Mjolnir GCS Deployment Utility")
    parser.add_argument("--web", action="store_true", help="Deploy static WASM web dashboard")
    parser.add_argument("--runs", action="store_true", help="Deploy missing local scan runs to GCS")
    parser.add_argument(
        "--include-usage",
        action="store_true",
        help="Include sensitive token usage telemetry files",
    )
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    load_dotenv(workspace_root)
    bucket_name = get_bucket_name()

    client = storage.Client()

    if args.web:
        deploy_web(workspace_root, client, bucket_name)
    elif args.runs:
        deploy_runs(workspace_root, client, bucket_name, include_usage=args.include_usage)
    else:
        print("Please specify --web or --runs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
