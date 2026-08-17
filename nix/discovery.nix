# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs, makeJob }:
let
  projectsDir = ../projects;
  testsDir = ../tests;

  # Scans a directory for `.nix` job files and makes each one into a runnable flake.
  # For tests, `-test` is appended to the end of the runnable flake name.
  scanJobsFolder = folderPath: project: devShell: targetNameFn:
    let
      filesList =
        if builtins.pathExists folderPath
        then builtins.attrNames (builtins.readDir folderPath)
        else [];

      processFile = fileAcc: fileName:
        let
          filePath = folderPath + "/${fileName}";
          nameWithoutExt = pkgs.lib.strings.removeSuffix ".nix" fileName;
          targetName = targetNameFn nameWithoutExt;
        in
          if pkgs.lib.strings.hasSuffix ".nix" fileName then
            fileAcc // {
              "${targetName}" = makeJob {
                inherit project devShell;
                job = import filePath;
              };
            }
          else
            fileAcc;
    in
      builtins.foldl' processFile {} filesList;

  projectsList =
    if builtins.pathExists projectsDir
    then builtins.attrNames (builtins.readDir projectsDir)
    else [];

  processProject = acc: projectDirName:
    let
      projectPath = projectsDir + "/${projectDirName}";
      projectNix = projectPath + "/project.nix";
      jobsPath = projectPath + "/jobs";
      shellNixPath = projectPath + "/shell.nix";
    in
      if builtins.pathExists projectNix then
        let
          projectImport = import projectNix;
          project = if builtins.isFunction projectImport then projectImport { inherit pkgs; } else projectImport;

          devShell =
            if project ? shell then
              (if builtins.isFunction (import project.shell) then (import project.shell) { inherit pkgs; } else import project.shell)
            else if builtins.pathExists shellNixPath then
              (if builtins.isFunction (import shellNixPath) then (import shellNixPath) { inherit pkgs; } else import shellNixPath)
            else null;

          jobsMap = scanJobsFolder jobsPath project devShell (name: "${project.repoName}-${name}");
        in
          acc // jobsMap
      else
        acc;

  discoveredProjects = builtins.foldl' processProject {} projectsList;

  testsProjectNix = testsDir + "/project.nix";
  testsJobsPath = testsDir + "/jobs";
  discoveredTests =
    if builtins.pathExists testsProjectNix then
      let
        projectImport = import testsProjectNix;
        project = if builtins.isFunction projectImport then projectImport { inherit pkgs; } else projectImport;
        devShell = null;
      in
        scanJobsFolder testsJobsPath project devShell (name:
          if pkgs.lib.strings.hasSuffix "-test" name
          then name
          else "${name}-test"
        )
    else {};
in
  discoveredProjects // discoveredTests
