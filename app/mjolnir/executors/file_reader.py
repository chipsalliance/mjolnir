# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Runner abstraction for reading local workspace files."""

import asyncio
from pathlib import Path
from constants import MAX_FILE_SIZE_BYTES


class FileReader:
    """Encapsulates safe file reading, size validation, and line range formatting."""

    def __init__(self, safe_path: Path) -> None:
        self.safe_path = safe_path

    def read(self, file_path: str, start_line: int = 1, end_line: int | None = None) -> str:
        """Reads file contents and returns formatted line range string."""
        file_size = self.safe_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return (
                f"Error: File '{file_path}' exceeds safety limit ({file_size // (1024 * 1024)}MB)."
            )

        try:
            with open(self.safe_path, "r", errors="ignore") as f:
                lines = f.readlines()

            total_lines = len(lines)
            start = max(1, start_line) - 1
            end = min(total_lines, end_line) if end_line is not None else total_lines

            if start >= total_lines:
                return f"Error: start_line ({start_line}) exceeds file length ({total_lines})."

            output_lines = [
                f"File: {file_path} (Showing lines {start + 1} to {end} of {total_lines} total lines)\n"
            ]
            for idx, line in enumerate(lines[start:end], start=start + 1):
                output_lines.append(f"{idx}: {line}")
            return "".join(output_lines)
        except Exception as e:
            return f"Error: Failed to read file: {str(e)}"

    async def read_async(
        self, file_path: str, start_line: int = 1, end_line: int | None = None
    ) -> str:
        """Asynchronously reads file contents and returns formatted line range string."""
        return await asyncio.to_thread(
            self.read, file_path, start_line=start_line, end_line=end_line
        )
