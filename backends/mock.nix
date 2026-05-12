# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  pkgs,
  mockResult ? ''
    [[vulnerabilities]]
    file = \"dummy.rs\"
    title = \"Dummy Vulnerability\"
    severity = \"Low\"
    location = \"Line 1\"
    description = \"Dummy description from mock backend.\"
    recommendation = \"Dummy recommendation.\"
  '',
}:
{
  name = "mock";
  run =
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
      METADATA_FILE="$(dirname "${output}")/metadata.toml"
      > "${output}"

      while IFS= read -r f; do
        if [ -f "${src}/$f" ]; then
          echo "Mocking analysis for $f..."
          echo "${mockResult}" >> "${output}"
        fi
      done < "${files}"
    '';

  runSingle =
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
