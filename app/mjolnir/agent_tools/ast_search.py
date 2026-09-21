# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from google.adk.tools import ToolContext

from executors.ast_grep import AstGrepRunner
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output
from utilities.logger import logger


@limit_tool_output
async def ast_search(
    pattern: str,
    lang: str,
    dir_path: str = ".",
    tool_context: ToolContext | None = None,
) -> str:
    """Performs structural abstract syntax tree (AST) search across the codebase using `ast-grep` (`sg`).

    Use this tool to match code structures, call patterns, or control-flow idioms regardless of
    whitespace or formatting (for example, finding all calls `memcpy($DST, $SRC, $LEN)`,
    unhardened comparisons `if ($ERR != kErrorOk)`, or specific struct initializers).
    Use `$META` to match a single AST node and `$$$ARGS` to match zero or more arguments/statements.

    Args:
        pattern: Structural code pattern using `ast-grep` syntax (e.g., `HARDENED_CHECK_EQ($A, $B)`).
        lang: Target language parser to use (e.g., `c`, `rust`, `cpp`, `verilog`).
        dir_path: Optional relative directory scope within the workspace (defaults to `.`).

    Returns:
        Matching source code snippets with file paths and line numbers.
    """
    code_dir = tool_context.state.get("code_dir", ".") if tool_context else "."
    try:
        search_path = resolve_workspace_path(dir_path, base_dir=code_dir)
    except ValueError as err:
        return f"Error: {err}"

    if not search_path.exists():
        return f"Error: Path '{dir_path}' does not exist."

    logger.debug(
        f"[Tool Execution] ast_search: pattern='{pattern}', lang='{lang}', dir_path='{dir_path}'"
    )
    runner = AstGrepRunner()
    return await runner.search_async(pattern, lang, search_path)
