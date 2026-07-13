# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import re
import subprocess
from utilities.agent_context import CURRENT_RUN_ID
from utilities.decorators import limit_tool_output


@limit_tool_output(max_chars=40000)
def ctags_search(
    symbol: str,
    dir_path: str = ".",
) -> str:
    """Finds the definition of a symbol across the codebase using Universal Ctags.

    Args:
        symbol: The exact name of the function, struct, macro, or variable to find.
        dir_path: The directory to search in. Defaults to ".".
    """
    code_dir = os.environ.get("CODE_DIR", ".")
    search_path = os.path.abspath(os.path.join(code_dir, dir_path))
    if not search_path.startswith(os.path.abspath(code_dir)):
        return "Error: Access denied. Path traversal detected."

    if not os.path.exists(search_path):
        return f"Error: Path '{dir_path}' does not exist."

    run_id = CURRENT_RUN_ID.get()
    prefix = f"[{run_id}] " if run_id else ""
    print(
        f"{prefix}[Tool Execution] ctags_search: symbol='{symbol}', dir_path='{dir_path}'",
        flush=True,
    )

    tags_file = os.path.join(search_path, "tags")

    # If a precomputed tags file exists, query it extremely fast using readtags
    if os.path.exists(tags_file):
        cmd = ["readtags", "-t", tags_file, "-e", symbol]
    else:
        # Dynamically generate the cross-reference output for the specific directory
        # -x cross-reference format, --_xformat defines a clean format: [kind] [file]:[line] [context]
        cmd = ["ctags", "-x", "--_xformat=%K %f:%n %S", "-R", search_path]

    try:
        res = subprocess.run(
            cmd,
            cwd=search_path,
            capture_output=True,
            text=True,
            timeout=15.0,
        )

        if res.returncode != 0 and "readtags" not in cmd[0]:
            return f"Error executing ctags: {res.stderr}"

        output = res.stdout

        # If we ran dynamic ctags, filter for the symbol manually
        if "readtags" not in cmd[0] and output:
            lines = output.splitlines()
            pattern = re.compile(rf"\b{re.escape(symbol)}\b")
            filtered_lines = [l for l in lines if pattern.search(l)]
            if not filtered_lines:
                return f"No definitions found for '{symbol}'."
            return f"Definitions for '{symbol}':\n" + "\n".join(filtered_lines[:50])

        elif output:
            return f"Definitions for '{symbol}':\n{output}"
        else:
            return f"No definitions found for '{symbol}'."

    except FileNotFoundError:
        return (
            "Error: 'ctags' (or 'readtags') is not installed in the environment. "
            "Please add 'universal-ctags' to your Nix environment."
        )
    except subprocess.TimeoutExpired:
        return "Error: ctags search timed out."
    except Exception as e:
        return f"Error executing ctags_search: {str(e)}"
