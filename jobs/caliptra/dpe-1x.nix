# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ../default_job.nix { inherit pkgs; } {
  name = "Caliptra DPE 1.x";
  workspaceDir = "/tmp/caliptra-dpe-1x-workspace";
  outputDir = "./output/caliptra/dpe-1x";
  backend = "gemini";

  target = {
    repoUrl = "https://github.com/chipsalliance/caliptra-dpe.git";
    repoName = "caliptra-dpe";
    commit = "runtime-1.2";
    fileCommand = "${pkgs.fd}/bin/fd -t f -e rs";
  };

  postExtract = ''
    echo "Caliptra DPE 1.x: Deleting non-Rust files..."
    cd "$CODE_DIR" && ${pkgs.fd}/bin/fd -t f -H -I -E '*.rs' -x rm {}
  '';
}
