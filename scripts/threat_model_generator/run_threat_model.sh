# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
#!/bin/bash

# --- Configuration ---
REPO_URL="https://github.com/lowRISC/opentitan.git"
COMMIT="earlgrey_1.0.0"
CLONE_DIR="/tmp/opentitan-threat-model-src"

THREAT_MODEL="THREAT_MODEL.md"
PROMPT="PROMPT.md"

# Define the specific subdirectories you want to include in the threat model
# (OpenTitan is massive, so we scope it to the critical secure boot & crypto paths)
TARGET_DIRS=(
	"sw/device/silicon_creator/rom"
	"sw/device/silicon_creator/rom_ext"
	"sw/device/silicon_creator/manuf"
	"sw/device/lib/crypto"
	"sw/device/lib/base"
	"sw/otbn/crypto"
)

# File extensions to analyze
EXTENSIONS=("*.c" "*.h" "*.rs" "*.sv")
# ---------------------

if [[ ! -f "$PROMPT" ]]; then
	echo "[!] Error: Could not find $PROMPT in the current directory."
	exit 1
fi

echo "=================================================="
echo " OpenTitan Automated Threat Model Generator"
echo "=================================================="

# 1. Clone and Checkout the Repository
if [[ ! -d "$CLONE_DIR" ]]; then
	echo "[*] Cloning OpenTitan repository..."
	git clone "$REPO_URL" "$CLONE_DIR"
else
	echo "[*] OpenTitan repository already exists at $CLONE_DIR. Fetching updates..."
	cd "$CLONE_DIR" || exit
	git fetch origin
	cd - >/dev/null || exit
fi

echo "[*] Checking out $COMMIT..."
cd "$CLONE_DIR" || exit
git checkout "origin/$COMMIT" -q
cd - >/dev/null || exit

# 2. Dynamically Generate File List
echo "[*] Dynamically discovering target files..."
TMP_FILE_LIST=$(mktemp)

for dir in "${TARGET_DIRS[@]}"; do
	full_dir="$CLONE_DIR/$dir"
	if [[ -d "$full_dir" ]]; then
		for ext in "${EXTENSIONS[@]}"; do
			find "$full_dir" -type f -name "$ext" >>"$TMP_FILE_LIST"
		done
	else
		echo "[!] Warning: Target directory $dir does not exist in this commit."
	fi
done

FILE_COUNT=$(wc -l <"$TMP_FILE_LIST")
echo "[+] Found $FILE_COUNT files to analyze."

# Initialize the threat model file
echo "Initializing $THREAT_MODEL..."
touch "$THREAT_MODEL"

echo "--------------------------------------------------"
echo " Starting Gemini Analysis (Tool-less mode)..."
echo "--------------------------------------------------"

# 3. Iterate and Analyze
current_file=1
while IFS= read -r target_file; do
	# Get the relative path for cleaner logs
	rel_path="${target_file#$CLONE_DIR/}"

	echo "[*] ($current_file/$FILE_COUNT) Analyzing: $rel_path"

	# Pipe file to Gemini, tell it NOT to use tools, and append stdout to THREAT_MODEL.md
	cat "$target_file" | GEMINI_SYSTEM_MD="$PWD/$PROMPT" /google/bin/releases/gemini-cli/tools/gemini \
		-m gemini-3.1-pro-preview \
		-p "I am providing the contents of $rel_path via stdin. Analyze it based on your system instructions. Output ONLY the raw markdown analysis. Do NOT use any external tools. I will handle appending the output." >>"$THREAT_MODEL"

	((current_file++))
done <"$TMP_FILE_LIST"

# Cleanup
rm "$TMP_FILE_LIST"

echo "=================================================="
echo " All files processed. Check $THREAT_MODEL."
echo "=================================================="
