# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Runner abstraction for ast-grep (sg) CLI tool."""

from pathlib import Path
from utilities.command import CommandRunner


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

        cmd_runner = CommandRunner(
            args=["sg", "--pattern", pattern, "--lang", lang, str(target_path)],
            cwd=target_path,
            timeout_sec=self.timeout,
        )
        success, output = cmd_runner.execute()
        if not success:
            return output

        if not output.strip():
            return f"No structural matches found for pattern '{pattern}' in {lang}."

        return output
