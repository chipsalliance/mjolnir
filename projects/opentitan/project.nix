# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "OpenTitan";
  repoName = "opentitan";
  repoUrl = "https://github.com/lowrisc/opentitan.git";
  requireGcsUpload = true;
  srcExtensions = [ "rs" "c" "h" "sv" ];
  threatModel = ../../app/mjolnir/providers/genai/threat-models/opentitan/THREAT_MODEL.md;
}