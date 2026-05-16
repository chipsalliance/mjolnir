# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import re
import argparse
from pathlib import Path


def load_filter_list(filter_path):
    """Reads the analysis files list to know which files are part of this job."""
    if not filter_path or not os.path.exists(filter_path):
        return None
    with open(filter_path, "r", encoding="utf-8") as f:
        # Strip lines and ignore blanks
        return {line.strip() for line in f if line.strip()}


def build_dependency_graph(src_dir, allowed_files=None):
    graph = {}
    include_pattern = re.compile(r'^\s*#\s*include\s+"([^"]+)"')

    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith((".c", ".h")):
                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(src_dir))

                # PRUNING: Skip if a filter list exists and this file isn't in it
                if allowed_files is not None and rel_path not in allowed_files:
                    continue

                dependencies = []
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            match = include_pattern.search(line)
                            if match:
                                dependencies.append(match.group(1))
                except Exception as e:
                    print(f"Warning: Could not read {rel_path}: {e}")

                if dependencies:
                    graph[rel_path] = dependencies

    return graph


def write_toml(graph, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("[dependencies]\n")
        for file_path, deps in graph.items():
            deps_str = ", ".join(f'"{d}"' for d in deps)
            f.write(f'"{file_path}" = [{deps_str}]\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract source code dependency graph."
    )
    parser.add_argument("--src", required=True, help="Source directory")
    parser.add_argument("--output", required=True, help="Output TOML file path")
    parser.add_argument(
        "--filter-list", help="Path to $ANALYSIS_FILES_FILE to prune results"
    )
    args = parser.parse_args()

    allowed_files = load_filter_list(args.filter_list)
    if allowed_files:
        print(
            f"Filtering graph context using {len(allowed_files)} active analysis files..."
        )

    graph = build_dependency_graph(args.src, allowed_files)
    write_toml(graph, args.output)

    print(f"Extracted dependency graph mapping {len(graph)} scoped C/C++ files.")
    print(f"Saved dependency TOML to: {args.output}")
