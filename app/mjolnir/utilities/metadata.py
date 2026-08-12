# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path

from utilities.git import get_head_commit


def write_metadata(
    run_dir: str,
    repo_url: str,
    model_name: str,
    ref: str,
    code_dir: str,
    timestamp_pretty: str,
    ingest_path: str = None,
    diff_base: str = None,
    auth_mode: str = None,
    gcp_project: str = None,
    gcp_location: str = None,
):
    """Resolves HEAD commit hash and dumps run metadata.json."""
    metadata_file = Path(run_dir) / "metadata.json"
    resolved_commit = get_head_commit(code_dir)

    if ingest_path:
        mode = "Ingestion"
    elif diff_base:
        mode = "PR Diff"
    else:
        mode = "Discovery"

    metadata = {
        "repo": repo_url,
        "model": model_name,
        "ref": ref or "HEAD",
        "target_commit": resolved_commit,
        "timestamp": timestamp_pretty,
        "mode": mode,
    }
    if auth_mode:
        metadata["auth_mode"] = auth_mode
    if gcp_project:
        metadata["gcp_project"] = gcp_project
    if gcp_location:
        metadata["gcp_location"] = gcp_location

    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
