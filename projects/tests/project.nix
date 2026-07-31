# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
let
  mockRepoBuilder = import ./nix/mock_repo.nix { inherit pkgs; };
  dummyRepo = mockRepoBuilder { enablePRDiff = true; };
in
{
  name = "Integration Tests";
  repoUrl = "file://${dummyRepo}";
  repoName = "tests";
  commit = "main";
  srcExtensions = [ "rs" ];
  provider = "mock";
}
