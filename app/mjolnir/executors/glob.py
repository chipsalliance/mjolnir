# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Runner abstraction for Glob file search."""

import asyncio
import fnmatch
from typing import Callable
from pathlib import Path
from utilities.git import GitOperation


class GlobRunner:
    """Encapsulates file listing, pattern matching, and result formatting for glob search."""

    def __init__(
        self,
        search_path: Path,
        code_dir: Path | str = ".",
        case_sensitive: bool = False,
        respect_git_ignore: bool = True,
    ) -> None:
        self.search_path = search_path
        self.code_dir = Path(code_dir).absolute()
        self.case_sensitive = case_sensitive
        self.respect_git_ignore = respect_git_ignore

    def filter_files(
        self,
        candidate_files: list[str],
        predicate: Callable[[str], bool],
    ) -> list[str]:
        """Filters candidate files using a closure predicate."""
        matched_files: list[str] = []
        for f in candidate_files:
            candidates = (
                [
                    f,
                    str(self.search_path.relative_to(self.code_dir)),
                    str(self.search_path),
                ]
                if self.search_path.is_file()
                else [f]
            )
            for cand in candidates:
                if predicate(cand):
                    matched_files.append(f)
                    break
        return matched_files

    def search(self, pattern: str, dir_path: str = ".") -> str:
        """Finds files matching pattern within search_path."""
        git_op = GitOperation(self.search_path, respect_git_ignore=self.respect_git_ignore)
        candidate_files = git_op.list_files()

        glob_predicate = (
            (lambda cand: fnmatch.fnmatchcase(cand, pattern))
            if self.case_sensitive
            else (lambda cand: fnmatch.fnmatchcase(cand.lower(), pattern.lower()))
        )

        matched_files = self.filter_files(candidate_files, glob_predicate)

        if not matched_files:
            return f"No files matching '{pattern}' found within '{dir_path}'."

        absolute_matches = (
            [str(self.search_path)]
            if self.search_path.is_file()
            else [str(self.search_path / m) for m in matched_files]
        )
        return (
            f"Found {len(absolute_matches)} file(s) matching '{pattern}' within '{dir_path}':\n"
            + "\n".join(absolute_matches)
        )

    async def search_async(self, pattern: str, dir_path: str = ".") -> str:
        """Finds files matching pattern within search_path asynchronously."""
        return await asyncio.to_thread(self.search, pattern, dir_path=dir_path)
