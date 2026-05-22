# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
{
  name,
  workspaceDir,
  outputDir,
  backend ? null,
  model ? "unused-testing-default",
  numFiles ? 10,
  enableGcsUpload ? false,
}:
import ../default_job.nix { inherit pkgs; } {
  inherit name workspaceDir outputDir backend enableGcsUpload model;
  agentDir = ../../agents/rust_auditor;
  parallel = 5;

  target = {
    repoUrl = "https://github.com/chipsalliance/caliptra-sw.git";
    repoName = "caliptra-sw";
    commit = "latest";
  };

  postExtract = ''
    echo "${name}: Update file list to only include first ${toString numFiles} Rust files..."

    # Find the first ${toString numFiles} Rust files from within CODE_DIR and update the list file
    cd "$CODE_DIR"
    # Dump to tmp file first to avoid SIGPIPE/pipefail crashes if fd is piped directly to head
    ${pkgs.fd}/bin/fd -H -e rs . > "$ANALYSIS_FILES_FILE.tmp"
    head -n ${toString numFiles} "$ANALYSIS_FILES_FILE.tmp" > "$ANALYSIS_FILES_FILE"
    rm "$ANALYSIS_FILES_FILE.tmp"
    cd "$TOP_DIR"
  '';
}
