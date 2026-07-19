# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output


@limit_tool_output(max_chars=40000)
def read_file(
    file_path: str,
    start_line: int = 1,
    end_line: int | None = None,
    tool_context=None,
) -> str:
    """Reads the contents of a file from the checked-out codebase, optionally filtering by line range.

    Args:
        file_path: The relative path of the file under the workspace/code directory.
        start_line: 1-indexed line to start reading from (inclusive).
        end_line: 1-indexed line to stop reading at (inclusive). If None, reads to end of file.
        tool_context: ADK ToolContext injected automatically by framework.
    """
    code_dir = tool_context.state.get("code_dir", ".")
    safe_path, err = resolve_workspace_path(file_path, base_dir=code_dir)
    if err or safe_path is None:
        return err or "Error: Invalid path."

    if not safe_path.exists() or not safe_path.is_file():
        return f"Error: File '{file_path}' does not exist or is not a regular file."

    print(
        f"[Tool Execution] read_file: {file_path} (lines {start_line} to {end_line if end_line else 'end'})",
        flush=True,
    )
    file_size = safe_path.stat().st_size
    if file_size > 10 * 1024 * 1024:
        return f"Error: File '{file_path}' exceeds safety limit ({file_size // (1024 * 1024)}MB)."

    try:
        with open(safe_path, "r", errors="ignore") as f:
            lines = f.readlines()

        total_lines = len(lines)
        start = max(1, start_line) - 1
        end = min(total_lines, end_line) if end_line is not None else total_lines

        if start >= total_lines:
            return (
                f"Error: start_line ({start_line}) exceeds file length ({total_lines})."
            )

        output_lines = [
            f"File: {file_path} (Showing lines {start + 1} to {end} of {total_lines} total lines)\n"
        ]
        for idx, line in enumerate(lines[start:end], start=start + 1):
            output_lines.append(f"{idx}: {line}")
        return "".join(output_lines)
    except Exception as e:
        return f"Error reading file: {str(e)}"
