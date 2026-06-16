# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
from utilities.decorators import limit_tool_output


@limit_tool_output(max_chars=40000)
def read_file(file_path: str, start_line: int = 1, end_line: int = None) -> str:
    """Reads the contents of a file from the checked-out codebase, optionally filtering by line range.

    Args:
        file_path: The relative path of the file under the workspace/code directory.
        start_line: 1-indexed line to start reading from (inclusive).
        end_line: 1-indexed line to stop reading at (inclusive). If None, reads to the end of the file.
    """
    code_dir = os.environ.get("CODE_DIR", ".")
    print(
        f" [Tool Execution] read_file: {file_path} (lines {start_line} to {end_line if end_line else 'end'})",
        flush=True,
    )
    safe_path = os.path.abspath(os.path.join(code_dir, file_path))
    if not safe_path.startswith(os.path.abspath(code_dir)):
        return "Error: Access denied. Path traversal detected."
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

        content = "".join(lines[start:end])
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"
