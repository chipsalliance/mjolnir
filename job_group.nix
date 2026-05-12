# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:

{ name, description, jobs }:
pkgs.writeShellScriptBin name ''
  set -euo pipefail

  echo "Starting execution: ${description}..."

  ${pkgs.lib.concatMapStringsSep "\n" (j: ''
    echo ""
    echo "=================================================="
    echo " Running job: ${j.name}"
    echo "=================================================="
    ${j.pkg}/bin/vuln-orchestrator
  '') jobs}

  echo ""
  echo "=================================================="
  echo "SUCCESS: ${description} complete!"
  echo "=================================================="
''
