# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Strict license header compliance checker."""

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

REQUIRED_LICENSE_HEADER = "SPDX-License-Identifier: Apache-2.0"

DEFAULT_IGNORE_FILENAMES = [
    "LICENSE",
    "pnpm-lock.yaml",
    "flake.lock",
    "MODULE.bazel.lock",
    "Cargo.lock",
    "package.json",
    ".gitignore",
    ".bazelignore",
    ".bazelversion",
]

DEFAULT_IGNORE_PATTERNS = [
    "*prompts/*",
    "*skills/*",
    "scripts/threat_model_generator/*.md",
]

N = 3


def check_file_license(file_path: Path) -> bool:
    """Returns True if the file contains the required license header in its top N lines."""
    if not file_path.is_file() or file_path.stat().st_size == 0:
        return True
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            top_lines = [f.readline() for _ in range(N)]
            return any(REQUIRED_LICENSE_HEADER in line for line in top_lines)
    except Exception:
        return False


def get_tracked_files(root_dir: Path) -> list[Path]:
    """Returns list of tracked repository files using git ls-files."""
    res = subprocess.run(
        ["git", "ls-files"],
        cwd=root_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    return [root_dir / line.strip() for line in res.stdout.splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Check license headers in source files.")
    parser.add_argument(
        "--ignore-filenames",
        nargs="*",
        default=DEFAULT_IGNORE_FILENAMES,
        help="Exact filenames to ignore",
    )
    parser.add_argument(
        "--ignore-patterns",
        nargs="*",
        default=DEFAULT_IGNORE_PATTERNS,
        help="Glob patterns of files or paths to ignore",
    )
    args = parser.parse_args()

    current = Path(__file__).resolve().parent
    root_dir = current.parent if (current.parent / "MODULE.bazel").exists() else current

    ignore_filenames = set(args.ignore_filenames)
    ignore_patterns = set(args.ignore_patterns)

    tracked_files = get_tracked_files(root_dir)
    missing_license_files = []

    for file_path in tracked_files:
        try:
            rel_path_str = str(file_path.relative_to(root_dir))
        except ValueError:
            rel_path_str = str(file_path)

        # Check explicit ignore list and glob patterns
        if file_path.name in ignore_filenames or any(
            fnmatch.fnmatch(file_path.name, pat) or fnmatch.fnmatch(rel_path_str, pat)
            for pat in ignore_patterns
        ):
            continue

        if not check_file_license(file_path):
            missing_license_files.append(rel_path_str)

    if missing_license_files:
        print(
            f"FAILED: Found {len(missing_license_files)} file(s) missing '{REQUIRED_LICENSE_HEADER}' in top {N} lines:"
        )
        for f in sorted(missing_license_files):
            print(f"  - {f}")
        sys.exit(1)

    print(f"PASSED: All checked source files contain '{REQUIRED_LICENSE_HEADER}'.")


if __name__ == "__main__":
    main()
