# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "Caliptra SW";
  repoName = "caliptra-sw";
  repoUrl = "https://github.com/chipsalliance/caliptra-sw.git";
  requireGcsUpload = true;
  srcExtensions = [ "rs" "c" "h" "sv" ];
  threatModel = ../../app/mjolnir/providers/genai/threat-models/caliptra/THREAT_MODEL.md;
}