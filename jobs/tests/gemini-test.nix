# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ./base-test.nix { inherit pkgs; } {
  name = "Gemini Test Hook";
  workspaceDir = "/tmp/gemini-test-workspace";
  outputDir = "./test-output/gemini-test";
  backend = "gemini";
  enableGcsUpload = false;
}
