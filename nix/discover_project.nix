# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs, mjolnirApp, projectDir, runner ? null }:
let
  projectNix = projectDir + "/project.nix";
  jobsDir = projectDir + "/jobs";

  makeJob = import ./orchestrator.nix;

  project =
    if builtins.pathExists projectNix then
      let
        projectImport = import projectNix;
      in
        if builtins.isFunction projectImport then projectImport { inherit pkgs; } else projectImport
    else
      throw "Mjolnir project.nix not found in ${toString projectDir}";

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
            inherit pkgs project runner;
            job = import filePath;
            mjolnir-app = mjolnirApp;
          };
        }
      else
        acc;
in
  builtins.foldl' processJobFile {} jobFiles
