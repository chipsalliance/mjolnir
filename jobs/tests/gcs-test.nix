# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ./base.nix { inherit pkgs; } {
  name = "gcs-test";
  workspaceDir = "/tmp/gcs-test-workspace";
  outputDir = "./test-output/gcs-test";
  backend = "mock";
  enableGcsUpload = true;
  numFiles = 1;
}
