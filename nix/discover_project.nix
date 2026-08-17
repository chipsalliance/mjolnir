# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  pkgs,
  mjolnirApp,
  projectDir,
  runner ? null,
  deployPackages ? {},
}:
let
  projectImport = import (projectDir + "/project.nix");
  project = if builtins.isFunction projectImport then projectImport { inherit pkgs; } else projectImport;
  jobsDir = projectDir + "/jobs";
  makeJob = import ./orchestrator.nix;

  jobFiles =
    if builtins.pathExists jobsDir then
      builtins.attrNames (builtins.readDir jobsDir)
    else
      [];

  processJobFile = acc: fileName:
    let
      filePath = jobsDir + "/${fileName}";
      jobName = pkgs.lib.strings.removeSuffix ".nix" fileName;
    in
      if pkgs.lib.strings.hasSuffix ".nix" fileName then
        acc // {
          "${jobName}" = makeJob {
            inherit pkgs project runner projectDir;
            job = import filePath;
            mjolnir-app = mjolnirApp;
          };
        }
      else
        acc;

  discoveredJobs = builtins.foldl' processJobFile {} jobFiles;
in
  discoveredJobs // (if runner != null then { inherit runner; } else {}) // deployPackages


