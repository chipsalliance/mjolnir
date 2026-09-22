# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import fnmatch
import os
from pathlib import Path

from utilities.logger import logger


def is_file_excluded(
    rel_path: str,
    exclude_dirs: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> bool:
    """Returns True if rel_path matches any excluded directory segment/prefix or glob pattern."""
    norm_path = rel_path.replace("\\", "/").lstrip("./")
    path_parts = Path(norm_path).parts
    file_name = Path(norm_path).name

    for raw_dir in exclude_dirs or []:
        clean_dir = raw_dir.replace("\\", "/").strip().strip("/")
        if not clean_dir:
            continue
        # If clean_dir contains a slash (e.g. "sw/device/tests"), match as a relative prefix;
        # otherwise (e.g. "tests" or "vendor"), match against any directory component in the path.
        if "/" in clean_dir:
            if norm_path == clean_dir or norm_path.startswith(f"{clean_dir}/"):
                return True
        elif clean_dir in path_parts[:-1]:
            return True

    for pattern in exclude_patterns or []:
        clean_pat = pattern.strip()
        if not clean_pat:
            continue
        if fnmatch.fnmatch(norm_path, clean_pat) or fnmatch.fnmatch(file_name, clean_pat):
            return True

    return False


def discover_source_files(
    code_dir: str,
    src_dirs: list[str],
    extensions: set[str],
    max_files: int | None = None,
    exclude_dirs: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[str]:
    """Finds all source files under the target directory matching the requested extensions and exclusion filters."""

    code_path = Path(code_dir).resolve()
    files_to_scan = []

    for s_dir in src_dirs:
        scan_path = (code_path / s_dir).resolve()
        if not scan_path.exists():
            continue
        for root, dirs, files in os.walk(scan_path):
            root_path = Path(root)
            # Skip hidden directories starting with '.' (like .git, .bazel, etc)
            if any(part.startswith(".") for part in root_path.parts):
                dirs[:] = []
                continue

            # Prune excluded subdirectories in-place before descending
            if exclude_dirs:
                kept_dirs = []
                for d in dirs:
                    candidate_dir = root_path / d
                    try:
                        rel_dir = str(candidate_dir.relative_to(code_path))
                    except ValueError:
                        rel_dir = str(candidate_dir)
                    if not is_file_excluded(f"{rel_dir}/placeholder", exclude_dirs=exclude_dirs):
                        kept_dirs.append(d)
                dirs[:] = kept_dirs

            for file in files:
                file_path = root_path / file
                ext = file_path.suffix.lstrip(".").lower()
                if ext in extensions:
                    try:
                        rel_path = str(file_path.relative_to(code_path))
                    except ValueError:
                        rel_path = str(file_path)
                    if is_file_excluded(rel_path, exclude_dirs, exclude_patterns):
                        continue
                    files_to_scan.append(rel_path)

    if max_files and isinstance(max_files, int) and len(files_to_scan) > max_files:
        logger.info(
            f"     [Config Loader] Limiting scan from {len(files_to_scan)} to first {max_files} files (maxFiles set)"
        )
        files_to_scan = files_to_scan[:max_files]

    return files_to_scan
