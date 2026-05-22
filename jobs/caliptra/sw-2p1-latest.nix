# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ./base.nix { inherit pkgs; } {
  name = "Caliptra SW Analysis";
  workspaceDir = "/tmp/caliptra-sw-workspace";
  outputDir = "./output/caliptra/sw-2p1";
  repoName = "caliptra-sw";
  repoUrl = "https://github.com/chipsalliance/caliptra-sw.git";
  commit = "latest";
  fileCommand = "${pkgs.fd}/bin/fd -t f -e rs --search-path rom/dev/src";
  contextFile = ../../threat-models/caliptra/THREAT_MODEL_FIRMWARE_SMALL.md;
}
