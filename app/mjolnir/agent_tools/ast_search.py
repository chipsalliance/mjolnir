# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import subprocess
from utilities.decorators import limit_tool_output


@limit_tool_output(max_chars=40000)
def ast_search(
    pattern: str,
    lang: str,
    dir_path: str = ".",
    tool_context=None,
) -> str:
    """Uses tree-sitter (via ast-grep / sg) to perform a structural syntax search (n-hop).

    This is much more powerful than regex. You can search for code structures.
    Example for finding all calls to a function: `ast_search("my_func($$$)", "c")`
    Example for finding all struct definitions: `ast_search("struct $A { $$$ }", "c")`

    Args:
        pattern: The ast-grep structural pattern to search for. ($$$ matches multiline/args, $A matches a variable).
        lang: The programming language (e.g., 'c', 'rust', 'python').
        dir_path: The directory to search in. Defaults to ".".
        tool_context: ADK ToolContext injected automatically by framework.
    """
    code_dir = tool_context.state.get("code_dir", ".")
    search_path = os.path.abspath(os.path.join(code_dir, dir_path))
    if not search_path.startswith(os.path.abspath(code_dir)):
        return "Error: Access denied. Path traversal detected."

    if not os.path.exists(search_path):
        return f"Error: Path '{dir_path}' does not exist."

    print(
        f"[Tool Execution] ast_search: pattern='{pattern}', lang='{lang}', dir_path='{dir_path}'",
        flush=True,
    )

    # Use ast-grep (sg) which is standard tree-sitter CLI
    cmd = ["sg", "--pattern", pattern, "--lang", lang, search_path]

    try:
        res = subprocess.run(
            cmd,
            cwd=search_path,
            capture_output=True,
            text=True,
            timeout=15.0,
        )

        output = res.stdout

        if res.returncode != 0 and not output:
            return f"Error executing ast-grep (sg): {res.stderr}"

        if not output.strip():
            return f"No structural matches found for pattern '{pattern}' in {lang}."

        lines = output.splitlines()
        max_lines = 100
        if len(lines) > max_lines:
            return (
                "\n".join(lines[:max_lines])
                + f"\n\n... [Truncated {len(lines) - max_lines} more lines]"
            )
        return output

    except FileNotFoundError:
        return (
            "Error: 'sg' (ast-grep) is not installed in the environment. "
            "Please add 'ast-grep' to your Nix environment to enable tree-sitter structural search."
        )
    except subprocess.TimeoutExpired:
        return "Error: ast-grep structural search timed out."
    except Exception as e:
        return f"Error executing ast_search: {str(e)}"
