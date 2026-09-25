# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "OpenPRoT";
  repoName = "openprot";
  repoUrl = "https://github.com/OpenPRoT/openprot.git";
  threatModel = ./threat_model.md;
  outputDir = "./test-out/results";
  workspaceDir = "./test-out/workspace";

  defaultModel = "gemini-3.8-flash";
  defaultRef = "main";
  defaultBatchSize = 64;
  defaultExtensions = [ "rs" "c" "h" ];
}
