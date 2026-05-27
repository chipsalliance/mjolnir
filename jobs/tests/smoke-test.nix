# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ./base.nix { inherit pkgs; } {
  name = "smoke-test";
  workspaceDir = "/tmp/smoke-test-workspace";
  outputDir = "./test-output/smoke-test";
  backend = "mock";
  model = "mock";
}
