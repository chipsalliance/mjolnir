# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from google.adk.tools import ToolContext

from executors.ctags import CtagsRunner
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output
from utilities.logger import logger


@limit_tool_output(max_chars=40000)
def ctags_search(
    symbol: str,
    dir_path: str = ".",
    tool_context: ToolContext | None = None,
) -> str:
    """Finds symbol definitions across codebase using Universal Ctags."""
    code_dir = tool_context.state.get("code_dir", ".") if tool_context else "."
    try:
        search_path = resolve_workspace_path(dir_path, base_dir=code_dir)
    except ValueError as err:
        return f"Error: {err}"

    if not search_path.exists():
        return f"Error: Path '{dir_path}' does not exist."

    logger.write(f"[Tool Execution] ctags_search: symbol='{symbol}', dir_path='{dir_path}'")
    runner = CtagsRunner()
    return runner.search(symbol, search_path)
