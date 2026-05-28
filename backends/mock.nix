# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  pkgs,
  mockResult ? ''
    {
      "vulnerabilities": [
        {
          "file": "dummy.rs",
          "title": "Dummy Vulnerability",
          "severity": "Low",
          "location": "Line 1",
          "description": "Dummy description from mock backend.",
          "recommendation": "Dummy recommendation.",
          "verdict": "Informational",
          "justification": "Mock run.",
          "attack_vector": ""
        }
      ]
    }
  '',
}:
{
  name = "mock";
  runBatchAuditor =
    {
      systemPrompt,
      src,
      files,
      output,
    }:
    ''
      echo "Running Mock backend individually on each file..."

      # Ensure output is empty initially
      # Initialize output with metadata if available
      METADATA_FILE="$(dirname "${output}")/metadata.json"
      > "${output}"

      # Write out mockResult directly as the raw JSON array to output
      echo '${mockResult}' > "${output}"
    '';

  runAdversarialReviewer =
    {
      systemPrompt,
      input,
      output,
    }:
    ''
      echo "Running Mock backend in Single-File Mode..."
      echo "${mockResult}" > "${output}"
    '';
}
