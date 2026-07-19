# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import subprocess
from utilities.decorators import limit_tool_output


def format_grep_output(
    raw_output: str, pattern: str, dir_path: str, filter_pattern: str = None
) -> str:
    lines = raw_output.splitlines()
    if not lines or raw_output == "No matches found.":
        return "No matches found."

    matches_by_file = {}
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


@limit_tool_output(max_chars=40000)
def grep_search(
    pattern: str,
    dir_path: str = ".",
    include_pattern: str = None,
    exclude_pattern: str = None,
    case_sensitive: bool = True,
    tool_context=None,
) -> str:
    """Searches for a regular expression pattern within file contents.

    Args:
        pattern: The regular expression (regex) to search for.
        dir_path: The path to the directory or file to search within. Defaults to ".".
        include_pattern: A glob pattern to filter which files are searched (when dir_path is a directory).
        exclude_pattern: A glob pattern to exclude files from the search.
        case_sensitive: Whether the search should be case-sensitive. Defaults to True.
        tool_context: ADK ToolContext injected automatically by framework.
    """
    code_dir = tool_context.state.get("code_dir", ".")
    search_path = os.path.abspath(os.path.join(code_dir, dir_path))
    if not search_path.startswith(os.path.abspath(code_dir)):
        return "Error: Access denied. Path traversal detected."

    if not os.path.exists(search_path):
        return f"Error: Path '{dir_path}' does not exist."

    print(
        f"[Tool Execution] grep_search: pattern='{pattern}', dir_path='{dir_path}', "
        f"include={include_pattern}, exclude={exclude_pattern}, case_sensitive={case_sensitive}",
        flush=True,
    )

    if os.path.isfile(search_path):
        cwd_path = os.path.dirname(search_path)
        target_path = os.path.basename(search_path)
    else:
        cwd_path = search_path
        target_path = "."

    try:
        # Try ripgrep first
        cmd = ["rg", "--line-number", "--no-heading", "--with-filename"]
        if not case_sensitive:
            cmd.append("-i")
        if include_pattern and not os.path.isfile(search_path):
            cmd.extend(["-g", include_pattern])
        if exclude_pattern:
            cmd.extend(["-g", f"!{exclude_pattern}"])
        cmd.extend([pattern, target_path])

        res = subprocess.run(
            cmd,
            cwd=cwd_path,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        stdout_content = res.stdout if res.stdout else "No matches found."
        lines = stdout_content.splitlines()
        truncated = False
        if len(lines) > 50:
            stdout_content = "\n".join(lines[:50])
            truncated = True

        formatted = format_grep_output(
            stdout_content, pattern, dir_path, include_pattern
        )
        if truncated:
            formatted += f"\n\n... [Warning: Output truncated. Showing first 50 matches out of {len(lines)} total. Please refine your query.]"
        return formatted

    except FileNotFoundError:
        # Fallback to git grep
        cmd = ["git", "grep", "-n"]
        if not case_sensitive:
            cmd.append("-i")
        cmd.append(pattern)

        pathspecs = []
        if os.path.isfile(search_path):
            pathspecs.append(target_path)
        elif include_pattern:
            pathspecs.append(include_pattern)
        else:
            pathspecs.append(".")

        if exclude_pattern:
            pathspecs.append(f":(exclude){exclude_pattern}")

        cmd.append("--")
        cmd.extend(pathspecs)

        res = subprocess.run(
            cmd,
            cwd=cwd_path,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        stdout_content = res.stdout if res.stdout else "No matches found."
        lines = stdout_content.splitlines()
        truncated = False
        if len(lines) > 50:
            stdout_content = "\n".join(lines[:50])
            truncated = True

        formatted = format_grep_output(
            stdout_content, pattern, dir_path, include_pattern
        )
        if truncated:
            formatted += f"\n\n... [Warning: Output truncated. Showing first 50 matches out of {len(lines)} total. Please refine your query.]"
        return formatted
    except Exception as e:
        return f"Error executing grep_search: {str(e)}"
