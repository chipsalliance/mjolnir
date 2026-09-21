# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Read file tool."""

from google.adk.tools import ToolContext

from executors.file_reader import FileReader
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output
from utilities.logger import logger


@limit_tool_output
async def read_file(
    file_path: str,
    start_line: int = 1,
    end_line: int | None = None,
    tool_context: ToolContext | None = None,
) -> str:
    """Reads the contents of a file from the checked-out codebase, optionally scoped to a line range.

    When inspecting definitions or call sites found via `ctags_search`, `ast_search`, or
    `grep_search`, specify `start_line` and `end_line` around the target line number to read the
    relevant function or struct efficiently without loading entire large files.

    Args:
        file_path: Relative path to the file from the repository root.
        start_line: 1-indexed starting line number to read from (defaults to `1`).
        end_line: Optional 1-indexed ending line number (inclusive). Omit to read to end of file.

    Returns:
        Line-numbered source file content for the requested range.
    """
    code_dir = tool_context.state.get("code_dir", ".") if tool_context else "."
    try:
        safe_path = resolve_workspace_path(file_path, base_dir=code_dir)
    except ValueError as err:
        return f"Error: {err}"

    if not safe_path.exists() or not safe_path.is_file():
        return f"Error: File '{file_path}' does not exist or is not a regular file."

    logger.debug(
        f"[Tool Execution] read_file: {file_path} (lines {start_line} to {end_line if end_line else 'end'})"
    )
    reader = FileReader(safe_path)
    return await reader.read_async(file_path, start_line=start_line, end_line=end_line)
