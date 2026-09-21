# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from google.adk.tools import ToolContext

from executors.ctags import CtagsRunner
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output
from utilities.logger import logger


@limit_tool_output
async def ctags_search(
    symbol: str,
    dir_path: str = ".",
    tool_context: ToolContext | None = None,
) -> str:
    """Performs an O(1) indexed lookup for symbol definitions across the codebase using Universal Ctags.

    Prefer this tool over `grep_search` whenever you need to locate where a function, struct,
    typedef, enum, macro, or global variable is defined. It queries the pre-built `.git/tags`
    index and returns exact `<kind> <file>:<line> <symbol><signature>` entries, which you can
    immediately inspect with `read_file(file_path, start_line, end_line)`.

    Args:
        symbol: Exact name of the C/Rust/SystemVerilog identifier (e.g., `rom_ext_verify`,
            `manifest_t`, `hardened_bool_t`).
        dir_path: Optional relative directory scope within the workspace (defaults to `.`).

    Returns:
        Formatted list of matching symbol definitions with file paths, line numbers, and signatures.
    """
    code_dir = tool_context.state.get("code_dir", ".") if tool_context else "."
    try:
        search_path = resolve_workspace_path(dir_path, base_dir=code_dir)
    except ValueError as err:
        return f"Error: {err}"

    if not search_path.exists():
        return f"Error: Path '{dir_path}' does not exist."

    logger.debug(f"[Tool Execution] ctags_search: symbol='{symbol}', dir_path='{dir_path}'")
    runner = CtagsRunner()
    return await runner.search_async(symbol, search_path)
