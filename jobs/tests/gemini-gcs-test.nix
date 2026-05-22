# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ./base.nix { inherit pkgs; } {
  name = "gemini-gcs-test";
  workspaceDir = "/tmp/gemini-gcs-test-workspace";
  outputDir = "./test-output/gemini-gcs-test";
  backend = "gemini";
  model = "gemini-2.5-pro";
  enableGcsUpload = true;
}
