# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "genai-ci-test";
  provider = "genai";
  model = "gemini-2.5-flash";
  diffBase = "HEAD~1";
  diffHead = "HEAD";
}
