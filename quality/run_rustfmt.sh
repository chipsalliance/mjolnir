#!/usr/bin/env bash
# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

if ! command -v cargo &>/dev/null; then
	echo "cargo not found on PATH; skipping rustfmt check."
	exit 0
fi

echo "Running cargo fmt --check..."
cargo fmt --check --manifest-path "${ROOT_DIR}/Cargo.toml"
echo "PASSED: All Rust source files are formatted cleanly."
