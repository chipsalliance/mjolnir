#!/usr/bin/env bash
# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

# Use Bazel-provided binary if available via environment, otherwise fall back to PATH
SHELLCHECK="${SHELLCHECK_BIN:-shellcheck}"

# Find root directory containing MODULE.bazel
ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Run shellcheck across all Git-tracked shell scripts
mapfile -t SCRIPTS < <(git -C "${ROOT_DIR}" ls-files '*.sh')

if [[ ${#SCRIPTS[@]} -eq 0 ]]; then
	echo "PASSED: No tracked shell scripts found to check."
	exit 0
fi

echo "Running shellcheck (${SHELLCHECK}) on ${#SCRIPTS[@]} shell script(s)..."
"${SHELLCHECK}" "${SCRIPTS[@]}"
echo "PASSED: All checked shell scripts passed shellcheck cleanly."
