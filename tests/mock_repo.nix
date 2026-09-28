# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
{ enablePRDiff ? true }:
pkgs.runCommand "dummy-test-git-repo" { buildInputs = [ pkgs.git ]; } ''
  mkdir -p $out
  cd $out
  git init --initial-branch=main
  git config user.name "Test Automaton"
  git config user.email "test@localhost"

  mkdir -p src
  cat << 'EOF' > src/lib.rs
// Safe Rust code: no buffer overflow possible
pub fn parse_config(config_str: &str) -> String {
    let trimmed = config_str.trim();
    let mutated = format!("config: {}", trimmed);
    mutated
}
EOF

  cat << 'EOF' > src/main.rs
// Unsafe integer underflow defect:
fn process_key(key_len: usize) -> usize {
    // If key_len is 0, this wraps around to usize::MAX
    let index = key_len - 1;
    index
}

fn main() {
    let result = process_key(0);
    println!("Index: {}", result);
}
EOF

  cat << 'EOF' > src/file3.rs
// Calls shared helper in main.rs
pub fn derive_offset(len: usize) -> usize {
    crate::process_key(len)
}
EOF
  echo '// Mock file 4' > src/file4.rs

  cat << 'EOF' > mock_report.csv
title,severity,location,description,recommendation,file
Buffer Overflow in parse_config,HIGH,src/lib.rs:3,A buffer overflow exists in parse_config due to unsafe string copy.,Use strncpy instead.,src/lib.rs
Integer Underflow in key_len,MEDIUM,src/main.rs:3,An integer underflow can happen if key_len is zero.,Add bound checks.,src/main.rs
Arithmetic wrap in derive_offset,MEDIUM,src/file3.rs:2,Calling derive_offset(0) delegates to an unnamed helper in another file that wraps around.,Validate len before calling helper.,src/file3.rs
EOF

  git add .
  git commit -m "Initial commit"

  ${if enablePRDiff then ''
    cat << 'EOF' > src/pr_diff_feature.rs
// Modified PR diff file for testing CI scanning mode
pub fn pr_diff_check(val: u32) -> bool {
    val > 100
}
EOF
    echo '// Updated lib line' >> src/lib.rs
    git add .
    git commit -m "PR feature changes"
  '' else ""}
''
