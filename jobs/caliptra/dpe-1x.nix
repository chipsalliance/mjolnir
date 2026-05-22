# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ./base.nix { inherit pkgs; } {
  name = "Caliptra DPE 1.x";
  workspaceDir = "/tmp/caliptra-dpe-1x-workspace";
  outputDir = "./output/caliptra/dpe-1x";
  repoName = "caliptra-dpe";
  repoUrl = "https://github.com/chipsalliance/caliptra-dpe.git";
  commit = "runtime-1.2";
}
