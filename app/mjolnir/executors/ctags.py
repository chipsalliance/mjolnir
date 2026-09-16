# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Runner abstraction for Universal Ctags CLI tool."""

import asyncio
import os
from pathlib import Path
import re
import threading
from utilities.command import CommandRunner, run_command_capture
from utilities.logger import logger


class CtagsRunner:
    """Encapsulates universal-ctags and readtags CLI execution."""

    _global_lock = threading.Lock()
    _locks: dict[str, threading.Lock] = {}

    def __init__(self, timeout: float | None = None) -> None:
        self.timeout = timeout

    def get_tags_path(self, search_path: Path) -> Path:
        """Returns the path to the ctags index file, preferring .git/tags to keep working trees clean."""
        git_dir = search_path / ".git"
        if git_dir.is_dir():
            return git_dir / "tags"
        existing_tags = search_path / "tags"
        if existing_tags.exists():
            return existing_tags
        return search_path / ".mjolnir_tags"

    def ensure_tags(self, search_path: Path) -> Path | None:
        """Ensures a universal-ctags index exists for search_path, generating it atomically if missing."""
        tags_file = self.get_tags_path(search_path)
        if tags_file.exists():
            return tags_file

        path_key = str(search_path.resolve())
        with self._global_lock:
            if path_key not in self._locks:
                self._locks[path_key] = threading.Lock()
            lock = self._locks[path_key]

        with lock:
            if tags_file.exists():
                return tags_file

            tmp_tags = tags_file.with_name(
                f"{tags_file.name}.tmp.{os.getpid()}.{threading.get_ident()}"
            )
            cmd = [
                "ctags",
                "--fields=+n+K+S",
                "-n",
                "-R",
                "-f",
                str(tmp_tags),
                ".",
            ]
            try:
                res = run_command_capture(cmd, cwd=str(search_path), timeout=self.timeout)
                if res.returncode == 0 and tmp_tags.exists():
                    tmp_tags.replace(tags_file)
                    logger.debug(f"Generated ctags index at {tags_file}")
                    return tags_file
                else:
                    if tmp_tags.exists():
                        tmp_tags.unlink(missing_ok=True)
            except Exception as e:
                logger.debug(f"Failed to pre-generate ctags index at {tags_file}: {e}")
                if tmp_tags.exists():
                    tmp_tags.unlink(missing_ok=True)
        return None

    async def ensure_tags_async(self, search_path: Path) -> Path | None:
        """Asynchronously ensures a ctags index exists for search_path."""
        return await asyncio.to_thread(self.ensure_tags, search_path)

    @staticmethod
    def _format_readtags_output(raw_output: str, symbol: str) -> str:
        """Formats tab-separated readtags output into concise '<kind> <file>:<line> <symbol><signature>' lines."""
        formatted: list[str] = []
        for line in raw_output.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                formatted.append(line)
                continue
            sym_name = parts[0]
            file_path = parts[1]
            line_num = parts[2].split(";")[0]
            kind = "symbol"
            signature = ""
            for field in parts[3:]:
                if field.startswith("kind:"):
                    kind = field[5:]
                elif field.startswith("signature:"):
                    signature = field[10:]
            formatted.append(f"{kind} {file_path}:{line_num} {sym_name}{signature}")
        return f"Definitions for '{symbol}':\n" + "\n".join(formatted)

    def search(self, symbol: str, search_path: Path) -> str:
        """Executes O(1) readtags lookup using cached tags index, falling back to ctags -x if unavailable."""
        tags_file = self.ensure_tags(search_path)

        if tags_file and tags_file.exists():
            cmd = ["readtags", "-t", str(tags_file), "-e", symbol]
        else:
            cmd = ["ctags", "-x", "--_xformat=%K %f:%n %S", "-R", str(search_path)]

        res = run_command_capture(cmd, cwd=str(search_path), timeout=self.timeout)
        output = res.stdout.strip() if res.stdout else ""

        if cmd[0] == "readtags":
            if res.returncode == 0 and output:
                return self._format_readtags_output(output, symbol)
            elif res.returncode == 1 or (res.returncode == 0 and not output):
                return f"No definitions found for '{symbol}'."
            else:
                err = res.stderr.strip() or f"Process exited with code {res.returncode}"
                return f"Error executing readtags: {err}"
        else:
            if res.returncode != 0:
                err = res.stderr.strip() or f"Process exited with code {res.returncode}"
                return f"Error executing ctags: {err}"
            if output:
                lines = output.splitlines()
                pattern = re.compile(rf"\b{re.escape(symbol)}\b")
                filtered_lines = [l for l in lines if pattern.search(l)]
                if not filtered_lines:
                    return f"No definitions found for '{symbol}'."
                return f"Definitions for '{symbol}':\n" + "\n".join(filtered_lines)
            return f"No definitions found for '{symbol}'."

    async def search_async(self, symbol: str, search_path: Path) -> str:
        """Executes readtags or ctags on search_path asynchronously."""
        return await asyncio.to_thread(self.search, symbol, search_path)
