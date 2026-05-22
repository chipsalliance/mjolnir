# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ../default_job.nix { inherit pkgs; } {
  name = "Caliptra DPE";
  workspaceDir = "/tmp/caliptra-dpe-workspace";
  outputDir = "./output/caliptra/dpe";
  backend = "gemini";

  target = {
    repoUrl = "https://github.com/chipsalliance/caliptra-dpe.git";
    repoName = "caliptra-dpe";
    commit = "latest";
    fileCommand = "${pkgs.fd}/bin/fd -t f -e rs";
  };

  postExtract = ''
    echo "Caliptra DPE: Deleting non-Rust files..."
    cd "$CODE_DIR" && ${pkgs.fd}/bin/fd -t f -H -I -E '*.rs' -x rm {}
    echo "Caliptra DPE: Removing xtask folder"
    cd "$CODE_DIR" && rm -r xtask/
  '';
}
