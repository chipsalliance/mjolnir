# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Runner abstraction for Universal Ctags CLI tool."""

from pathlib import Path
import re
from utilities.command import CommandRunner


class CtagsRunner:
    """Encapsulates universal-ctags and readtags CLI execution."""

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def search(self, symbol: str, search_path: Path) -> str:
        """Executes readtags or ctags on search_path."""
        tags_file = search_path / "tags"

        if tags_file.exists():
            cmd = ["readtags", "-t", str(tags_file), "-e", symbol]
        else:
            cmd = ["ctags", "-x", "--_xformat=%K %f:%n %S", "-R", str(search_path)]

        cmd_runner = CommandRunner(cmd, cwd=search_path, timeout=self.timeout)
        success, output = cmd_runner.execute(tool_name="ctags")
        if not success and "readtags" not in cmd[0]:
            return output

        if "readtags" not in cmd[0] and output:
            lines = output.splitlines()
            pattern = re.compile(rf"\b{re.escape(symbol)}\b")
            filtered_lines = [l for l in lines if pattern.search(l)]
            if not filtered_lines:
                return f"No definitions found for '{symbol}'."
            return f"Definitions for '{symbol}':\n" + "\n".join(filtered_lines)
        elif output:
            return f"Definitions for '{symbol}':\n{output}"
        else:
            return f"No definitions found for '{symbol}'."
