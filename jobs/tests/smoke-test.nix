# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ../default_job.nix { inherit pkgs; } {
  name = "Smoke Test";
  workspaceDir = "/tmp/smoke-test-workspace";
  outputDir = "./test-output/smoke-test";
  backend = "mock";
  enableGcsUpload = false;

  target = {
    repoUrl = "https://github.com/chipsalliance/caliptra-sw.git";
    repoName = "caliptra-sw";
    commit = "latest";
    fileCommand = "echo 'api/src/lib.rs'"; # Just analyze one file for quick smoke test
  };

  postExtract = ''
    echo "Smoke Test: Post Extract Hook"
  '';
}
