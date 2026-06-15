# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import fnmatch
import subprocess


def glob_files(pattern: str) -> list[str]:
    """Finds files matching a wildcard pattern in the workspace.
    Limited to a maximum of 100 results to avoid exhausting token context.

    Args:
        pattern: A glob pattern, e.g., '**/*.rs' or 'src/*.c'.
    """
    code_dir = os.environ.get("CODE_DIR", ".")
    print(f" [Tool Execution] glob_files: pattern='{pattern}'", flush=True)
    matches = []
    for root, _, filenames in os.walk(code_dir):
        for filename in fnmatch.filter(filenames, pattern):
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, code_dir)
            matches.append(rel_path)
    return matches[:100]
