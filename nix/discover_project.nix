# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  pkgs,
  mjolnirApp,
  projectDir,
  devShell ? null,
  deployPackages ? {},
}:
let
  projectImport = import (projectDir + "/project.nix");
  project = if builtins.isFunction projectImport then projectImport { inherit pkgs; } else projectImport;
  jobsDir = projectDir + "/jobs";
  makeJob = import ./orchestrator.nix;

  projectShellPath = projectDir + "/shell.nix";
  discoveredShell =
    if devShell != null then devShell
    else if project ? shell then
      (if builtins.isFunction (import project.shell) then (import project.shell) { inherit pkgs; } else import project.shell)
    else if builtins.pathExists projectShellPath then
      (if builtins.isFunction (import projectShellPath) then (import projectShellPath) { inherit pkgs; } else import projectShellPath)
    else null;

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
            inherit pkgs project projectDir;
            devShell = discoveredShell;
            job = import filePath;
            mjolnir-app = mjolnirApp;
          };
        }
      else
        acc;

  discoveredJobs = builtins.foldl' processJobFile {} jobFiles;
in
  discoveredJobs // (if discoveredShell != null then { devShell = discoveredShell; } else {}) // deployPackages


