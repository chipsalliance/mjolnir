# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Lean, decoupled loader for historical Open vulnerabilities from GCS or local directories."""

import json
from pathlib import Path
from typing import Any, Optional

from constants import RUNS_SUBDIR, VULNERABILITIES_FILENAME
from data.status import Status
from utilities.logger import logger


def _extract_open_findings(
    raw_vulns: list[dict[str, Any]], job_name: str, run_id: str
) -> list[dict[str, Any]]:
    """Filters a run's findings to concise representations of active Open vulnerabilities."""
    open_findings = []
    for idx, item in enumerate(raw_vulns):
        if not isinstance(item, dict):
            continue
        status_val = str(item.get("status", Status.OPEN.value)).strip().lower()
        if status_val == Status.OPEN.value.lower():
            vuln_id = str(item.get("id") or idx)
            open_findings.append(
                {
                    "canonical_ref": f"{job_name}/{run_id}/{vuln_id}",
                    "id": vuln_id,
                    "job": job_name,
                    "run_id": run_id,
                    "file": item.get("file", ""),
                    "location": item.get("location", ""),
                    "title": item.get("title", ""),
                    "severity": item.get("severity", ""),
                    "description": item.get("description", ""),
                    "attack_vector": item.get("attack_vector", ""),
                }
            )
    return open_findings


def load_local_historical_open_findings(
    results_dir: Path, current_run_dir: Optional[str] = None
) -> list[dict[str, Any]]:
    """Scans local runs directory for prior Open findings."""
    runs_root = results_dir / RUNS_SUBDIR if (results_dir / RUNS_SUBDIR).exists() else results_dir
    if not runs_root.exists():
        return []

    curr_path = Path(current_run_dir).resolve() if current_run_dir else None
    results = []

    for vuln_file in runs_root.glob(f"*/*/*/{VULNERABILITIES_FILENAME}"):
        run_dir = vuln_file.parent
        if curr_path and run_dir.resolve() == curr_path:
            continue
        try:
            with open(vuln_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            parts = vuln_file.parts
            run_id = parts[-2]
            job_name = parts[-3]
            results.extend(_extract_open_findings(data, job_name, run_id))
        except Exception as e:
            logger.debug(f"Failed to read historical local run {vuln_file}: {e}")

    return results


def load_gcs_historical_open_findings(
    bucket_name: str, project_name: str, current_run_dir: Optional[str] = None
) -> list[dict[str, Any]]:
    """Loads historical Open findings for project_name from a GCS bucket."""
    try:
        from google.cloud import storage
    except ImportError:
        logger.warning("google-cloud-storage not installed; skipping GCS historical loading.")
        return []

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name.replace("gs://", "").strip("/"))
        prefix = f"{RUNS_SUBDIR}/{project_name}/"
        curr_run_id = Path(current_run_dir).name if current_run_dir else None

        blobs = client.list_blobs(bucket, prefix=prefix)
        results = []
        for blob in blobs:
            if not blob.name.endswith(f"/{VULNERABILITIES_FILENAME}"):
                continue
            parts = blob.name.split("/")
            run_id = parts[-2] if len(parts) >= 2 else "unknown"
            job_name = parts[-3] if len(parts) >= 3 else "default"
            if curr_run_id and run_id == curr_run_id:
                continue

            try:
                content = blob.download_as_text()
                data = json.loads(content)
                results.extend(_extract_open_findings(data, job_name, run_id))
            except Exception as e:
                logger.debug(f"Failed to load GCS run {blob.name}: {e}")

        return results
    except Exception as err:
        logger.warning(f"Could not load historical runs from GCS bucket '{bucket_name}': {err}")
        return []


async def load_historical_open_vulnerabilities(
    bucket: Optional[str] = None,
    project_name: Optional[str] = None,
    project_output_dir: Optional[str] = None,
    current_run_dir: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Optional historical loader: checks GCS bucket if specified, else checks local runs."""
    if bucket:
        clean_bucket = bucket.strip()
        if clean_bucket.startswith("gs://") or not Path(clean_bucket).exists():
            return load_gcs_historical_open_findings(
                clean_bucket, project_name or "default", current_run_dir
            )
        return load_local_historical_open_findings(Path(clean_bucket), current_run_dir)

    if project_output_dir and Path(project_output_dir).exists():
        return load_local_historical_open_findings(Path(project_output_dir), current_run_dir)

    return []
