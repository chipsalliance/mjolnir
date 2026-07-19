# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Runner abstraction for Universal Ctags CLI tool."""

from pathlib import Path
import re
import subprocess


class CtagsRunner:
    """Encapsulates universal-ctags and readtags CLI execution."""

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def search(self, symbol: str, search_path: Path) -> str:
        """Executes readtags or ctags on search_path.

        Since Nix guarantees ctags is installed, execution fails fast if missing.
        """
        tags_file = search_path / "tags"

        if tags_file.exists():
            cmd = ["readtags", "-t", str(tags_file), "-e", symbol]
        else:
            cmd = ["ctags", "-x", "--_xformat=%K %f:%n %S", "-R", str(search_path)]

        res = subprocess.run(
            cmd,
            cwd=str(search_path),
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )

        if res.returncode != 0 and "readtags" not in cmd[0]:
            return f"Error executing ctags: {res.stderr}"

        output = res.stdout
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
