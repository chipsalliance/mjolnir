# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Glob file search tool."""

from google.adk.tools import ToolContext

from executors.glob import GlobRunner
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output
from utilities.logger import logger


@limit_tool_output
async def glob(
    pattern: str,
    dir_path: str = ".",
    case_sensitive: bool = False,
    respect_git_ignore: bool = True,
    tool_context: ToolContext | None = None,
) -> str:
    """Finds files matching specific glob patterns across the workspace."""
    base_dir = tool_context.state.get("code_dir", ".") if tool_context else "."
    try:
        search_path = resolve_workspace_path(dir_path, base_dir=base_dir)
    except ValueError as err:
        return f"Error: {err}"

    if not search_path.exists():
        return f"Error: Path '{dir_path}' does not exist."

    logger.debug(f"[Tool Execution] glob: pattern='{pattern}', dir_path='{dir_path}'")
    runner = GlobRunner(
        search_path,
        code_dir=base_dir,
        case_sensitive=case_sensitive,
        respect_git_ignore=respect_git_ignore,
    )
    return await runner.search_async(pattern, dir_path=dir_path)
