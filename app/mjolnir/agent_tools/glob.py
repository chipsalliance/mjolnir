# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Glob file search tool."""

import fnmatch
import os
from pathlib import Path
import subprocess
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output


def _list_candidate_files(search_path: Path, respect_git_ignore: bool) -> list[str]:
    """Collects candidate files using git ls-files or directory walk."""
    if search_path.is_file():
        target_name = search_path.name
        cwd_path = str(search_path.parent)
        if respect_git_ignore:
            try:
                res = subprocess.run(
                    [
                        "git",
                        "ls-files",
                        "-c",
                        "-o",
                        "--exclude-standard",
                        "--",
                        target_name,
                    ],
                    cwd=cwd_path,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5.0,
                )
                if res.stdout.strip():
                    return [target_name]
            except Exception:
                pass
        return [target_name]

    if respect_git_ignore:
        try:
            res = subprocess.run(
                ["git", "ls-files", "-c", "-o", "--exclude-standard"],
                cwd=str(search_path),
                capture_output=True,
                text=True,
                check=True,
                timeout=5.0,
            )
            return res.stdout.splitlines()
        except Exception:
            pass

    files: list[str] = []
    for root, _, filenames in os.walk(str(search_path)):
        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(root, filename), str(search_path))
            files.append(rel_path)
    return files


def _filter_glob_matches(
    files: list[str],
    pattern: str,
    search_path: Path,
    code_dir: Path,
    case_sensitive: bool,
) -> list[str]:
    """Filters file paths against a glob pattern."""
    matches: list[str] = []
    for f in files:
        candidates = (
            [f, str(search_path.relative_to(code_dir)), str(search_path)]
            if search_path.is_file()
            else [f]
        )
        for cand in candidates:
            match = (
                fnmatch.fnmatchcase(cand, pattern)
                if case_sensitive
                else fnmatch.fnmatchcase(cand.lower(), pattern.lower())
            )
            if match:
                matches.append(f)
                break
    return matches


@limit_tool_output(max_chars=40000)
def glob(
    pattern: str,
    dir_path: str = ".",
    case_sensitive: bool = False,
    respect_git_ignore: bool = True,
    respect_gemini_ignore: bool = True,
    tool_context=None,
) -> str:
    """Finds files matching specific glob patterns across the workspace."""
    base_dir = tool_context.state.get("code_dir", ".")
    search_path, err = resolve_workspace_path(dir_path, base_dir=base_dir)
    if err or search_path is None:
        return err or "Error: Invalid path."

    if not search_path.exists():
        return f"Error: Path '{dir_path}' does not exist."

    print(
        f"[Tool Execution] glob: pattern='{pattern}', dir_path='{dir_path}'",
        flush=True,
    )
    candidate_files = _list_candidate_files(search_path, respect_git_ignore)
    code_dir_path = Path(base_dir).resolve()
    matched_files = _filter_glob_matches(
        candidate_files, pattern, search_path, code_dir_path, case_sensitive
    )

    if not matched_files:
        return f"No files matching '{pattern}' found within '{dir_path}'."

    absolute_matches = (
        [str(search_path)]
        if search_path.is_file()
        else [str((search_path / m).resolve()) for m in matched_files]
    )
    display_matches = absolute_matches[:500]
    res_str = (
        f"Found {len(absolute_matches)} file(s) matching '{pattern}' within '{dir_path}':\n"
        + "\n".join(display_matches)
    )
    if len(absolute_matches) > 500:
        res_str += f"\n\n... [Warning: Only first 500 matches shown out of {len(absolute_matches)} total]"
    return res_str
