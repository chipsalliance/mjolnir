# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import fnmatch
import subprocess


def read_file(path: str) -> str:
    """Reads the entire contents of a file from the checked-out codebase.
    Limited to a maximum of 100,000 characters to avoid exhausting token context.

    Args:
        path: The relative path of the file under the workspace/code directory.
    """
    code_dir = os.environ.get("CODE_DIR", ".")
    print(f" [Tool Execution] read_file: {path}", flush=True)
    safe_path = os.path.abspath(os.path.join(code_dir, path))
    if not safe_path.startswith(os.path.abspath(code_dir)):
        return "Error: Access denied. Path traversal detected."
    try:
        # Read at most 100,000 characters (~25k tokens) to prevent token context explosion
        with open(safe_path, "r") as f:
            content = f.read(100000)
            if len(content) == 100000:
                content += "\n\n... [Warning: File truncated. Only the first 100,000 characters were read to prevent token budget overload.]"
            return content
    except Exception as e:
        return f"Error reading file: {str(e)}"
