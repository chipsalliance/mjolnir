# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Runner abstraction for ast-grep (sg) CLI tool."""

from pathlib import Path
from utilities.command import run_command_capture


class AstGrepRunner:
    """Encapsulates ast-grep CLI execution for structural syntax code search."""

    def __init__(self, search_path: Path | None = None, timeout: float = 15.0) -> None:
        self.search_path = search_path
        self.timeout = timeout

    def search(self, pattern: str, lang: str, search_path: Path | None = None) -> str:
        """Executes sg CLI on search_path."""
        target_path = search_path or self.search_path
        if target_path is None:
            return "Error executing ast-grep (sg): search_path must be specified."

        cmd = ["sg", "--pattern", pattern, "--lang", lang, str(target_path)]
        res = run_command_capture(
            cmd,
            cwd=str(target_path),
            timeout=self.timeout,
        )

        output = res.stdout
        if res.returncode != 0 and not output:
            return f"Error executing ast-grep (sg): {res.stderr}"

        if not output.strip():
            return f"No structural matches found for pattern '{pattern}' in {lang}."

        return output
