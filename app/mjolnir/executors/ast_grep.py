# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Runner abstraction for ast-grep (sg) CLI tool."""

from pathlib import Path
import subprocess


class AstGrepRunner:
    """Encapsulates ast-grep CLI execution for structural syntax code search."""

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def search(self, pattern: str, lang: str, search_path: Path) -> str:
        """Executes sg CLI on search_path.

        Since Nix guarantees ast-grep ('sg') is installed, execution fails fast if missing.
        """
        cmd = ["sg", "--pattern", pattern, "--lang", lang, str(search_path)]
        res = subprocess.run(
            cmd,
            cwd=str(search_path),
            capture_output=True,
            text=True,
            timeout=self.timeout,
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
