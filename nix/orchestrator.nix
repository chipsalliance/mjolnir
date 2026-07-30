# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs, project, job, mjolnir-app, runner ? null }:
let
  jobSpec = {
    project = {
      inherit (project) name repoName repoUrl srcExtensions;
      threatModel = project.threatModel or null;
    };

    job = {
      inherit (job) name;
      model = job.model or project.model or "gemini-3.6-flash";
      provider = job.provider or project.provider or "adk";
      batchSize = job.batchSize or 64;
      branch = job.branch or null;
      tag = job.tag or null;
      commit = job.commit or null;
      srcDirs = job.srcDirs or [ "." ];
      extensions = job.extensions or [ "c" "h" "cpp" "cc" "rs" "go" "py" ];
      maxFiles = job.maxFiles or null;
      requireGcsUpload = job.requireGcsUpload or project.requireGcsUpload or false;
      cmd = job.cmd or null;
      ingestionReport = job.ingestionReport or null;
    };

    config = {
      workspaceDir = "./workspace/${project.repoName}/${pkgs.lib.replaceStrings [ " " ] [ "_" ] job.name}";
      outputDir = "./output/runs/${project.repoName}/${pkgs.lib.replaceStrings [ " " ] [ "_" ] job.name}";
      projectOutputDir = "./output/runs/${project.repoName}";
    };
  };

  # 2. Serialize to JSON in Nix store
  jobSpecFile = pkgs.writeText "mjolnir-job-spec-${project.repoName}-${job.name}.json" (builtins.toJSON jobSpec);

  # 5. Assemble execution script
  launcher = pkgs.writeShellScriptBin "mjolnir-orchestrator-${project.repoName}-${pkgs.lib.replaceStrings [ " " ] [ "_" ] job.name}" ''
    set -e
    
    # Inject project-specific compiler tools into PATH
    ${pkgs.lib.optionalString (runner != null) ''
      export PATH="${runner}/bin:$PATH"
    ''}

    exec ${mjolnir-app}/bin/mjolnir-run --spec "${jobSpecFile}" "$@"
  '';
in
  launcher
