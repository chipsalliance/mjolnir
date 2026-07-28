# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from executors.ctags import CtagsRunner
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output
from utilities.logger import logger


@limit_tool_output(max_chars=40000)
def ctags_search(
    symbol: str,
    dir_path: str = ".",
    tool_context=None,
) -> str:
    """Finds symbol definitions across codebase using Universal Ctags."""
    code_dir = tool_context.state.get("code_dir", ".")
    search_path, err = resolve_workspace_path(dir_path, base_dir=code_dir)
    if err or search_path is None:
        return err or "Error: Invalid search path."

    if not search_path.exists():
        return f"Error: Path '{dir_path}' does not exist."

    logger.write(f"[Tool Execution] ctags_search: symbol='{symbol}', dir_path='{dir_path}'")
    runner = CtagsRunner()
    return runner.search(symbol, search_path)
