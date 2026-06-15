# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "Caliptra DPE";
  repoName = "caliptra-dpe";
  repoUrl = "https://github.com/chipsalliance/caliptra-dpe.git";
  srcExtensions = [ "rs" "go" ];
  threatModel = ../../app/mjolnir/providers/genai/threat-models/caliptra/THREAT_MODEL.md;
}