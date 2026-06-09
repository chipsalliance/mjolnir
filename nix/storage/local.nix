# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs, path }:
{
  name = "local";
  upload =
    { runDir }:
    ''
      echo "Results are already in local path ${runDir} (target base: ${path})"
    '';
}
