# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ./base.nix { inherit pkgs; } {
  name = "Caliptra MCU SW Analysis";
  workspaceDir = "/tmp/caliptra-mcu-sw-workspace";
  outputDir = "./output/caliptra/mcu-sw-2p0";
  repoName = "caliptra-mcu-sw";
  repoUrl = "https://github.com/chipsalliance/caliptra-mcu-sw.git";
  commit = "latest";
}
