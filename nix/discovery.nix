# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs, makeJob, runners }:
let
  projectsDir = ../projects;
  projectsList = builtins.attrNames (builtins.readDir projectsDir);

  processProject = acc: projectDirName:
    let
      projectPath = projectsDir + "/${projectDirName}";
      projectNix = projectPath + "/project.nix";
      
      jobsPath = projectPath + "/jobs";
      nixPath = projectPath + "/nix";
    in
      if builtins.pathExists projectNix then
        let
          projectImport = import projectNix;
          project = if builtins.isFunction projectImport then projectImport { inherit pkgs; } else projectImport;
          
          runner = runners.${project.repoName} or null;

          scanFolder = folderPath: targetNameFn:
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
                        inherit project runner;
                        job = import filePath;
                      };
                    }
                  else
                    fileAcc;
            in
              builtins.foldl' processFile {} filesList;

          jobsMap = scanFolder jobsPath (name:
            if project.repoName == "tests"
            then "${name}-test"
            else "${project.repoName}-${name}"
          );
        in
          acc // jobsMap
      else
        acc;
in
  builtins.foldl' processProject {} projectsList
