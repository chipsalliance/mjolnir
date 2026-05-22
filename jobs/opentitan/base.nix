# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
{ subjobName, searchPaths, subdir, extensions ? [ "c" "h" "s" ], timeout ? 3600, backend ? "gemini" }:
let
  # Helper to build fd flags for extensions: [ "c" "h" "s" ] -> "-e c -e h -e s"
  fdExtFlags = pkgs.lib.concatMapStringsSep " " (ext: "-e ${ext}") extensions;
  # Helper to build fd exclude flags: [ "c" "h" "s" ] -> "-E '*.c' -E '*.h' -E '*.s'"
  fdExcludeFlags = pkgs.lib.concatMapStringsSep " " (ext: "-E '*.${ext}'") extensions;
  fdSearchFlags = pkgs.lib.concatMapStringsSep " " (path: "--search-path ${path}") searchPaths;
in
import ../default_job.nix { inherit pkgs; } {
  name = "OpenTitan Earlgrey A2 SW Scan - ${subjobName}";
  workspaceDir = "/tmp/opentitan-workspace/${subdir}";
  outputDir = "./output/opentitan/${subdir}";
  agentDir = ../../agents/c_auditor;
  inherit timeout;
  inherit backend;
  contextFile = ../../threat-models/opentitan/THREAT_MODEL_FIRMWARE_SMALL.md;

  target = {
    repoUrl = "https://github.com/lowrisc/opentitan";
    repoName = "opentitan";
    commit = "earlgrey_1.0.0";
    fileCommand = "${pkgs.fd}/bin/fd -t f ${fdExtFlags} ${fdSearchFlags} -E '*test*' -E '*mock*'";
  };

  postExtract = ''
    echo "Deleting non-target files..."
    cd "$CODE_DIR" && ${pkgs.fd}/bin/fd -t f -H -I ${fdExcludeFlags} -x rm {}
  '';
}
