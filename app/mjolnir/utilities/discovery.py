# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
from utilities.logger import logger


def discover_source_files(code_dir: str, job) -> list:
    """Finds all source files under the target directory matching the requested extensions, optionally limiting count."""

    extensions = job.get("extensions") or ["rs", "c", "h"]
    src_dirs = job.get("srcDirs") or ["."]
    max_files = job.get("maxFiles")

    files_to_scan = []
    for s_dir in src_dirs:
        scan_path = os.path.abspath(os.path.join(code_dir, s_dir))
        if not os.path.exists(scan_path):
            continue
        for root, _, files in os.walk(scan_path):
            # Skip hidden directories starting with '.' (like .git, .bazel, etc)
            if any(part.startswith(".") for part in root.split(os.sep)):
                continue
            for file in files:
                ext = os.path.splitext(file)[1].lstrip(".").lower()
                if ext in extensions:
                    rel_path = os.path.relpath(os.path.join(root, file), code_dir)
                    files_to_scan.append(rel_path)

    if max_files and isinstance(max_files, int) and len(files_to_scan) > max_files:
        logger.write(
            f"     [Config Loader] Limiting scan from {len(files_to_scan)} to first {max_files} files (maxFiles set)",
        )
        files_to_scan = files_to_scan[:max_files]

    return files_to_scan
