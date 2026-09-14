# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "adk-ollama-test";
  srcDirs = [ "src" ];
  maxFiles = 2;
  model = "ollama/gemma4:31b";
  batchSize = 1;
  extensions = [ "rs" ];
}
