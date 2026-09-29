# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "OpenTitan";
  repoName = "opentitan";
  repoUrl = "https://github.com/lowrisc/opentitan.git";
  threatModel = ./threat_model.md;
  outputDir = "./test-out/results";
  workspaceDir = "./test-out/workspace";

  defaultModel = "gemini-3.8-flash";
  defaultRef = "earlgrey_1.0.0";
  defaultMode = "full";
  defaultBatchSize = 64;
  defaultExtensions = [ "rs" "c" "h" "sv" ];
  defaultExcludeDirs = [
    "e2e"
    "test"
    "tests"
    "testdata"
    "sigverify_tests"
    "dv"
    "fuzz"
  ];
  defaultExcludePatterns = [
    "*_test.c"
    "*_test.h"
    "*_test.rs"
    "*_test.sv"
    "*_functest.c"
    "*_functest.h"
    "*_unittest.c"
    "*_unittest.h"
    "*_cryptotest.c"
    "*_test_*.c"
    "*_test_*.h"
    "*_unittest_*.h"
    "*_fuzzer_*.h"
    "*_testlib.h"
    "mock_*.c"
    "mock_*.h"
    "test_*.c"
    "test_*.h"
  ];
}
