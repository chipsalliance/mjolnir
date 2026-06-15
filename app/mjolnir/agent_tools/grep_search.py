# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import fnmatch
import subprocess


def grep_search(query: str, path: str = ".") -> str:
    """Searches for a regex or string pattern across files in the workspace.
    Limited to a maximum of 100 results to avoid exhausting token context.

    Args:
        query: The search term or regex pattern.
        path: Optional relative subdirectory to limit the search.
    """
    code_dir = os.environ.get("CODE_DIR", ".")
    print(f" [Tool Execution] grep_search: query='{query}', path='{path}'", flush=True)
    search_path = os.path.abspath(os.path.join(code_dir, path))
    if not search_path.startswith(os.path.abspath(code_dir)):
        return "Error: Access denied. Path traversal detected."
    rel_search_path = os.path.relpath(search_path, code_dir)
    try:
        res = subprocess.run(
            ["rg", "--line-number", "--no-heading", query, rel_search_path],
            cwd=code_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        stdout_content = res.stdout if res.stdout else "No matches found."
        lines = stdout_content.splitlines()
        if len(lines) > 100:
            return (
                "\n".join(lines[:100])
                + f"\n\n... [Warning: Output truncated. Found {len(lines)} matches. Please refine your query to be more specific.]"
            )
        return stdout_content
    except FileNotFoundError:
        res = subprocess.run(
            ["git", "grep", "-n", query, "--", rel_search_path],
            cwd=code_dir,
            capture_output=True,
            text=True,
        )
        stdout_content = res.stdout if res.stdout else "No matches found."
        lines = stdout_content.splitlines()
        if len(lines) > 100:
            return (
                "\n".join(lines[:100])
                + f"\n\n... [Warning: Output truncated. Found {len(lines)} matches. Please refine your query to be more specific.]"
            )
        return stdout_content
