# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "adk-claude-test";
  srcDirs = [ "src" ];
  maxFiles = 2;
  model = "claude-3-5-sonnet";
  batchSize = 1;
  extensions = [ "rs" ];
}
