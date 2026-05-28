# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Shared sandboxed workspace analysis tools for LLMs."""

import os
import fnmatch
import subprocess

CODE_DIR = os.environ.get("CODE_DIR", ".")


def read_file(path: str) -> str:
    """Reads the entire contents of a file from the checked-out codebase.

    Args:
        path: The relative path of the file under the workspace/code directory.
    """
    print(f" [Tool Execution] read_file: {path}", flush=True)
    safe_path = os.path.abspath(os.path.join(CODE_DIR, path))
    if not safe_path.startswith(os.path.abspath(CODE_DIR)):
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


def grep_search(query: str, path: str = ".") -> str:
    """Searches for a regex or string pattern across files in the workspace.

    Args:
        query: The search term or regex pattern.
        path: Optional relative subdirectory to limit the search.
    """
    print(f" [Tool Execution] grep_search: query='{query}', path='{path}'", flush=True)
    search_path = os.path.abspath(os.path.join(CODE_DIR, path))
    if not search_path.startswith(os.path.abspath(CODE_DIR)):
        return "Error: Access denied. Path traversal detected."
    try:
        res = subprocess.run(
            ["rg", "--line-number", "--no-heading", query, search_path],
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
            ["git", "grep", "-n", query], cwd=CODE_DIR, capture_output=True, text=True
        )
        stdout_content = res.stdout if res.stdout else "No matches found."
        lines = stdout_content.splitlines()
        if len(lines) > 100:
            return (
                "\n".join(lines[:100])
                + f"\n\n... [Warning: Output truncated. Found {len(lines)} matches. Please refine your query to be more specific.]"
            )
        return stdout_content


def glob_files(pattern: str) -> list[str]:
    """Finds files matching a wildcard pattern in the workspace.

    Args:
        pattern: A glob pattern, e.g., '**/*.rs' or 'src/*.c'.
    """
    print(f" [Tool Execution] glob_files: pattern='{pattern}'", flush=True)
    matches = []
    for root, _, filenames in os.walk(CODE_DIR):
        for filename in fnmatch.filter(filenames, pattern):
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, CODE_DIR)
            matches.append(rel_path)
    return matches[:100]
