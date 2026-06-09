# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ./base.nix { inherit pkgs; } {
  name = "gemini-test";
  workspaceDir = "/tmp/gemini-test-workspace";
  outputDir = "./test-output/gemini-test";
  backend = "gemini";
  model = "gemini-3.5-flash";
}
