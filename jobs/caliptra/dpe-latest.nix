# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ./base.nix { inherit pkgs; } {
  name = "Caliptra DPE";
  workspaceDir = "/tmp/caliptra-dpe-workspace";
  outputDir = "./output/caliptra/dpe";
  repoName = "caliptra-dpe";
  repoUrl = "https://github.com/chipsalliance/caliptra-dpe.git";
  commit = "latest";
  postExtractExtra = ''
    echo "Caliptra DPE: Removing xtask folder"
    cd "$CODE_DIR" && rm -r xtask/
  '';
}
