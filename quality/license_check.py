# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Strict license header compliance checker."""

import argparse
import subprocess
import sys
from pathlib import Path

REQUIRED_LICENSE_HEADER = "SPDX-License-Identifier: Apache-2.0"


def check_file_license(file_path: Path) -> bool:
    """Returns True if the file contains the required license header in its top 5 lines."""
    if not file_path.is_file() or file_path.stat().st_size == 0:
        return True
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            top_lines = [f.readline() for _ in range(5)]
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
    parser.add_argument("--extensions", nargs="*", default=[], help="File extensions to check")
    parser.add_argument("--filenames", nargs="*", default=[], help="Exact filenames to check")
    parser.add_argument(
        "--ignore-filenames", nargs="*", default=[], help="Exact filenames to ignore"
    )
    args = parser.parse_args()

    current = Path(__file__).resolve().parent
    root_dir = current.parent if (current.parent / "MODULE.bazel").exists() else current

    extensions = set(args.extensions)
    filenames = set(args.filenames)
    ignore_filenames = set(args.ignore_filenames)

    tracked_files = get_tracked_files(root_dir)
    missing_license_files = []

    for file_path in tracked_files:
        if file_path.name in ignore_filenames:
            continue
        if file_path.suffix in extensions or file_path.name in filenames:
            if not check_file_license(file_path):
                try:
                    rel_path = file_path.relative_to(root_dir)
                except ValueError:
                    rel_path = file_path
                missing_license_files.append(str(rel_path))

    if missing_license_files:
        print(
            f"FAILED: Found {len(missing_license_files)} file(s) missing '{REQUIRED_LICENSE_HEADER}' in top 5 lines:"
        )
        for f in sorted(missing_license_files):
            print(f"  - {f}")
        sys.exit(1)

    print(f"PASSED: All checked source files contain '{REQUIRED_LICENSE_HEADER}' in top 5 lines.")


if __name__ == "__main__":
    main()
