# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "Caliptra MCU SW";
  repoName = "caliptra-mcu-sw";
  repoUrl = "https://github.com/chipsalliance/caliptra-mcu-sw.git";
  requireGcsUpload = true;
  srcExtensions = [ "rs" "c" "h" "sv" ];
  threatModel = ../../app/mjolnir/providers/genai/threat-models/caliptra/THREAT_MODEL.md;
}