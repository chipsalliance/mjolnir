# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import json
from utilities.git import get_head_commit


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
    resolved_commit = get_head_commit(code_dir)

    metadata = {
        "repo": repo_url,
        "model": model_name,
        "ref": ref or "HEAD",
        "target_commit": resolved_commit,
        "timestamp": timestamp_pretty,
    }
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
