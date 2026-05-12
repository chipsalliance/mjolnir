# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
# NOTE: This backend is currently a PLACEHOLDER and is NOT YET WORKING OR TESTED.
{ pkgs }:
{
  name = "claude";
  run =
    {
      systemPrompt,
      src,
      output,
    }:
    ''
      echo "Running Claude backend on ${src}..."
      echo "# Claude Audit Report" > "${output}"
      echo "Simulated Claude analysis complete." >> "${output}"
    '';
}
