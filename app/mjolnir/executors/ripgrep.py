# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Runner abstraction for Ripgrep (rg) CLI tool."""

import asyncio
import json
from pathlib import Path
from utilities.command import CommandRunner, run_command_capture


def format_grep_output(
    raw_output: str, pattern: str, dir_path: str, filter_pattern: str | None = None
) -> str:
    """Formats structured ripgrep JSON output into grouped file matches."""
    matches_by_file: dict[str, list[tuple[int, str]]] = {}

    for line in raw_output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if isinstance(entry, dict) and entry.get("type") == "match":
            data = entry.get("data", {})
            file_path = data.get("path", {}).get("text", "")
            line_num = data.get("line_number", 0)
            line_content = data.get("lines", {}).get("text", "").rstrip("\r\n")
            if file_path:
                matches_by_file.setdefault(file_path, []).append((line_num, line_content))

    if not matches_by_file:
        return "No matches found."

    total_matches = sum(len(m) for m in matches_by_file.values())
    filter_info = f' (filter: "{filter_pattern}")' if filter_pattern else ""

    output = [
        f'Found {total_matches} matches for pattern "{pattern}" in path "{dir_path}"{filter_info}:',
        "---",
    ]
    for filename, matches in matches_by_file.items():
        output.append(f"File: {filename}")
        for line_num, content in matches:
            output.append(f"L{line_num}: {content}")
        output.append("---")

    if len(output) > 2:
        output.pop()  # Remove trailing "---"

    return "\n".join(output)


class RipgrepRunner:
    """Encapsulates ripgrep (rg) CLI execution and formatting for regex code search."""

    def __init__(
        self,
        case_sensitive: bool = True,
        show_line_numbers: bool = True,
        timeout: float | None = None,
    ) -> None:
        self.case_sensitive = case_sensitive
        self.show_line_numbers = show_line_numbers
        self.timeout = timeout

    def search(
        self,
        pattern: str,
        search_path: Path,
        dir_path: str = ".",
        include_pattern: str | None = None,
        exclude_pattern: str | None = None,
    ) -> str:
        """Executes ripgrep CLI on search_path and formats output."""
        is_file = search_path.is_file()
        cwd_path = str(search_path.parent) if is_file else str(search_path)
        target_path = search_path.name if is_file else "."

        cmd = ["rg", "--json"]
        if not self.case_sensitive:
            cmd.append("-i")
        if include_pattern and not is_file:
            cmd.extend(["-g", include_pattern])
        if exclude_pattern:
            cmd.extend(["-g", f"!{exclude_pattern}"])
        cmd.extend([pattern, target_path])

        res = run_command_capture(cmd, cwd=cwd_path, timeout=self.timeout)
        if res.returncode == 0:
            return format_grep_output(res.stdout or "", pattern, dir_path, include_pattern)
        elif res.returncode == 1:
            return "No matches found."
        else:
            err = res.stderr.strip() or f"Process exited with code {res.returncode}"
            return f"Error executing rg: {err}"

    async def search_async(
        self,
        pattern: str,
        search_path: Path,
        dir_path: str = ".",
        include_pattern: str | None = None,
        exclude_pattern: str | None = None,
    ) -> str:
        """Executes ripgrep CLI on search_path asynchronously and formats output."""
        return await asyncio.to_thread(
            self.search,
            pattern,
            search_path,
            dir_path=dir_path,
            include_pattern=include_pattern,
            exclude_pattern=exclude_pattern,
        )
