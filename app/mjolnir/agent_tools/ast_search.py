# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from executors.ast_grep import AstGrepRunner
from security.path_sanitizer import resolve_workspace_path
from utilities.decorators import limit_tool_output


@limit_tool_output(max_chars=40000)
def ast_search(
    pattern: str,
    lang: str,
    dir_path: str = ".",
    tool_context=None,
) -> str:
    """Uses tree-sitter (via ast-grep / sg) to perform structural syntax search."""
    code_dir = tool_context.state.get("code_dir", ".")
    search_path, err = resolve_workspace_path(dir_path, base_dir=code_dir)
    if err or search_path is None:
        return err or "Error: Invalid search path."

    if not search_path.exists():
        return f"Error: Path '{dir_path}' does not exist."

    print(
        f"[Tool Execution] ast_search: pattern='{pattern}', lang='{lang}', dir_path='{dir_path}'",
        flush=True,
    )
    runner = AstGrepRunner()
    return runner.search(pattern, lang, search_path)
