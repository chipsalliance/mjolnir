# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "genai-gemini-gcs-test";
  model = "gemini-2.5-flash";
  maxFiles = 5;
  srcDirs = [ "src" ];
  extensions = [ "rs" ];
  requireGcsUpload = true;
  provider = "genai";
}
