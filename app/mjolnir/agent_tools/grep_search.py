# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Grep search tool."""

from google.adk.tools import ToolContext

from executors.ripgrep import RipgrepRunner
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output
from utilities.logger import logger


@limit_tool_output(max_chars=40000)
def grep_search(
    pattern: str,
    dir_path: str = ".",
    include_pattern: str | None = None,
    exclude_pattern: str | None = None,
    case_sensitive: bool = True,
    tool_context: ToolContext | None = None,
) -> str:
    """Searches for a regular expression pattern within file contents."""
    code_dir = tool_context.state.get("code_dir", ".") if tool_context else "."
    try:
        search_path = resolve_workspace_path(dir_path, base_dir=code_dir)
    except ValueError as err:
        return f"Error: {err}"

    if not search_path.exists():
        return f"Error: Path '{dir_path}' does not exist."

    logger.write(
        f"[Tool Execution] grep_search: pattern='{pattern}', dir_path='{dir_path}', "
        f"include={include_pattern}, exclude={exclude_pattern}, case_sensitive={case_sensitive}"
    )

    runner = RipgrepRunner(case_sensitive=case_sensitive)
    return runner.search(
        pattern,
        search_path,
        dir_path=dir_path,
        include_pattern=include_pattern,
        exclude_pattern=exclude_pattern,
    )
