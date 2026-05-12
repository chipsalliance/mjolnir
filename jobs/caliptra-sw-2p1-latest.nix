# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ./default_job.nix { inherit pkgs; } {
  name = "Caliptra SW Analysis";
  workspaceDir = "/tmp/caliptra-sw-workspace";
  outputDir = "./caliptra-sw-2p1-output";
  backend = "gemini";
  contextFile = ../threat-models/caliptra/THREAT_MODEL_FIRMWARE_SMALL.md;

  target = {
    repoUrl = "https://github.com/chipsalliance/caliptra-sw.git";
    repoName = "caliptra-sw";
    commit = "latest";
    fileCommand = "${pkgs.fd}/bin/fd -t f -e rs --search-path rom/dev/src";
  };

  postExtract = ''
    echo "Caliptra SW Analysis: Deleting non-Rust files..."
    cd "$CODE_DIR" && ${pkgs.fd}/bin/fd -t f -H -I -E '*.rs' -x rm {}
  '';
}
