# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Grep search tool."""

from google.adk.tools import ToolContext

from executors.ripgrep import RipgrepRunner
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output
from utilities.logger import logger


@limit_tool_output
async def grep_search(
    pattern: str,
    dir_path: str = ".",
    include_pattern: str | None = None,
    exclude_pattern: str | None = None,
    case_sensitive: bool = True,
    tool_context: ToolContext | None = None,
) -> str:
    """Searches for a regular expression or literal pattern within file contents using `ripgrep` (`rg`).

    Use this tool to locate call sites, cross-references, string literals, register names, or
    comments across the codebase. For jumping directly to a function, struct, typedef, or macro
    definition, prefer `ctags_search` first; for structural syntax matching, consider `ast_search`.

    Args:
        pattern: Regular expression pattern to search for (e.g., `rom_ext_verify\\(`).
        dir_path: Optional relative directory scope to narrow the search (e.g., `sw/device/silicon_creator`).
        include_pattern: Optional glob filter for included filenames (e.g., `*.h`, `*.c`).
        exclude_pattern: Optional glob filter to exclude paths (e.g., `*_unittest.cc`, `*test*`).
        case_sensitive: Whether the regex match is case-sensitive (defaults to `True`).

    Returns:
        Matching lines formatted with relative file paths and 1-indexed line numbers.
    """
    code_dir = tool_context.state.get("code_dir", ".") if tool_context else "."
    try:
        search_path = resolve_workspace_path(dir_path, base_dir=code_dir)
    except ValueError as err:
        return f"Error: {err}"

    if not search_path.exists():
        return f"Error: Path '{dir_path}' does not exist."

    logger.debug(
        f"[Tool Execution] grep_search: pattern='{pattern}', dir_path='{dir_path}', "
        f"include={include_pattern}, exclude={exclude_pattern}, case_sensitive={case_sensitive}"
    )

    runner = RipgrepRunner(case_sensitive=case_sensitive)
    return await runner.search_async(
        pattern,
        search_path,
        dir_path=dir_path,
        include_pattern=include_pattern,
        exclude_pattern=exclude_pattern,
    )
