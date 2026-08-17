# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "genai-gemini-test";
  srcDirs = [ "src" ];
  maxFiles = 5;
  model = "gemini-3.6-flash";
  provider = "genai";
  extensions = [ "rs" ];
}
