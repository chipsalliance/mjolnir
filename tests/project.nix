# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
let
  mockRepoBuilder = import ./nix/mock_repo.nix { inherit pkgs; };
  dummyRepo = mockRepoBuilder { enablePRDiff = true; };
in
{
  name = "Integration Tests";
  repoName = "tests";
  repoUrl = "file://${dummyRepo}";
  commit = "main";
  outputDir = "./test-out/results";
  workspaceDir = "./test-out/workspace";

  defaultModel = "mock";
  defaultProvider = "mock";
  defaultBatchSize = 64;
  defaultExtensions = [ "rs" ];
}
