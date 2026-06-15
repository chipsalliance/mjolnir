# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import json
from utilities.command import run_command_capture


def write_metadata(
    run_dir: str,
    repo_url: str,
    model_name: str,
    ref: str,
    code_dir: str,
    timestamp_pretty: str,
):
    """Resolves HEAD commit hash and dumps run metadata.json."""
    metadata_file = os.path.join(run_dir, "metadata.json")
    try:
        resolved_commit = run_command_capture(
            ["git", "rev-parse", "HEAD"], cwd=code_dir, check=False
        )
        if not resolved_commit:
            resolved_commit = "unknown"
    except Exception:
        resolved_commit = "unknown"

    metadata = {
        "repo": repo_url,
        "model": model_name,
        "ref": ref or "HEAD",
        "target_commit": resolved_commit,
        "timestamp": timestamp_pretty,
    }
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
