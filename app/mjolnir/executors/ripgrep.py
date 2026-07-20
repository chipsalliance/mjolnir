# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Runner abstraction for Ripgrep (rg) CLI tool."""

from pathlib import Path
from utilities.command import run_command_capture


def format_grep_output(
    raw_output: str, pattern: str, dir_path: str, filter_pattern: str | None = None
) -> str:
    """Formats raw ripgrep output into grouped file matches."""
    lines = raw_output.splitlines()
    if not lines or raw_output == "No matches found.":
        return "No matches found."

    matches_by_file: dict[str, list[tuple[str, str]]] = {}
    for line in lines:
        try:
            parts = line.split(":", 2)
            if len(parts) < 3:
                continue
            filename, line_num, content = parts
            if filename not in matches_by_file:
                matches_by_file[filename] = []
            matches_by_file[filename].append((line_num, content))
        except ValueError:
            continue

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
        timeout: float = 5.0,
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

        cmd = ["rg"]
        if self.show_line_numbers:
            cmd.extend(["--line-number", "--no-heading", "--with-filename"])
        if not self.case_sensitive:
            cmd.append("-i")
        if include_pattern and not is_file:
            cmd.extend(["-g", include_pattern])
        if exclude_pattern:
            cmd.extend(["-g", f"!{exclude_pattern}"])
        cmd.extend([pattern, target_path])

        try:
            res = run_command_capture(
                cmd,
                cwd=cwd_path,
                timeout=self.timeout,
            )
            stdout_content = res.stdout if res.stdout else "No matches found."
            return format_grep_output(
                stdout_content, pattern, dir_path, include_pattern
            )
        except Exception as e:
            return f"Error executing ripgrep: {str(e)}"
