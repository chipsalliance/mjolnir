# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "OpenTitan";
  repoName = "opentitan";
  repoUrl = "https://github.com/lowrisc/opentitan.git";
  threatModel = ./threat_model.md;
  outputDir = "./test-out/results";
  workspaceDir = "./test-out/workspace";

  defaultModel = "gemini-3.6-flash";
  defaultProvider = "adk";
  defaultBatchSize = 64;
  defaultExtensions = [ "rs" "c" "h" "sv" ];
}