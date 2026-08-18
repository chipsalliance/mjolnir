# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "Caliptra MCU SW";
  repoName = "caliptra-mcu-sw";
  repoUrl = "https://github.com/chipsalliance/caliptra-mcu-sw.git";
  outputDir = "./test-out/results";
  workspaceDir = "./test-out/workspace";

  defaultModel = "gemini-3.6-flash";
  defaultProvider = "adk";
  defaultBatchSize = 64;
  defaultExtensions = [ "rs" "c" "h" "sv" ];
}