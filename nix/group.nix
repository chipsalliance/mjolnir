# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
{ name, description, jobs }:
pkgs.writeShellScriptBin name ''
  set -euo pipefail

  echo "[BEGIN] Group: ${description}"

  ${pkgs.lib.concatMapStringsSep "\n" (r: ''
    echo ""
    echo ">>> Running job target: ${r.name}"
    ${r}/bin/${r.name} "$@"
  '') jobs}

  echo ""
  echo "[END] Group: ${name}"
''
