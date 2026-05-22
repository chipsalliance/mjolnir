# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ../default_job.nix { inherit pkgs; } {
  name = "Caliptra MCU SW Analysis";
  workspaceDir = "/tmp/caliptra-mcu-sw-workspace";
  outputDir = "./output/caliptra/mcu-sw-2p0";
  backend = "gemini";

  target = {
    repoUrl = "https://github.com/chipsalliance/caliptra-mcu-sw.git";
    repoName = "caliptra-mcu-sw";
    commit = "latest";
    fileCommand = "${pkgs.fd}/bin/fd -t f -e rs";
  };

  postExtract = ''
    echo "Caliptra MCU SW Analysis: Deleting non-Rust files..."
    cd "$CODE_DIR" && ${pkgs.fd}/bin/fd -t f -H -I -E '*.rs' -x rm {}
  '';
}
