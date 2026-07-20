# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Read file tool."""

from executors.file_reader import FileReader
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output
from utilities.logger import logger


@limit_tool_output(max_chars=40000)
def read_file(
    file_path: str,
    start_line: int = 1,
    end_line: int | None = None,
    tool_context=None,
) -> str:
    """Reads the contents of a file from the checked-out codebase, optionally filtering by line range."""
    code_dir = tool_context.state.get("code_dir", ".") if tool_context else "."
    safe_path, err = resolve_workspace_path(file_path, base_dir=code_dir)
    if err or safe_path is None:
        return err or "Error: Invalid path."

    if not safe_path.exists() or not safe_path.is_file():
        return f"Error: File '{file_path}' does not exist or is not a regular file."

    logger.write(
        f"[Tool Execution] read_file: {file_path} (lines {start_line} to {end_line if end_line else 'end'})"
    )
    reader = FileReader(safe_path)
    return reader.read(file_path, start_line=start_line, end_line=end_line)
