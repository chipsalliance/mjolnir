# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs, project, job, mjolnir-app, devShell ? null, ... }:
let
  model = job.model or project.defaultModel or (throw "Mjolnir: No model specified for job '${job.name or "unknown"}' (set 'model' in job.nix or 'defaultModel' in project.nix).");
  provider = job.provider or project.defaultProvider or (throw "Mjolnir: No provider specified for job '${job.name or "unknown"}' (set 'provider' in job.nix or 'defaultProvider' in project.nix).");
  batchSize = job.batchSize or project.defaultBatchSize or (throw "Mjolnir: No batchSize specified for job '${job.name or "unknown"}' (set 'batchSize' in job.nix or 'defaultBatchSize' in project.nix).");
  extensions = job.extensions or project.defaultExtensions or (throw "Mjolnir: No extensions specified for job '${job.name or "unknown"}' (set 'extensions' in job.nix or 'defaultExtensions' in project.nix).");
  outputDir = project.outputDir or (throw "Mjolnir: No 'outputDir' specified for project '${project.name or "unknown"}' (set 'outputDir' in project.nix).");
  workspaceDir = project.workspaceDir or (throw "Mjolnir: No 'workspaceDir' specified for project '${project.name or "unknown"}' (set 'workspaceDir' in project.nix).");

  jobSpec = {
    project = {
      inherit (project) name repoName repoUrl;
      threatModel = project.threatModel or null;
    };

    job = {
      inherit (job) name;
      inherit model provider batchSize extensions;
      branch = job.branch or null;
      tag = job.tag or null;
      commit = job.commit or null;
      srcDirs = job.srcDirs or [ "." ];
      maxFiles = job.maxFiles or null;
      cmd = job.cmd or null;
      ingestionReport = job.ingestionReport or null;
      diffBase = job.diffBase or null;
      diffHead = job.diffHead or "HEAD";
    };

    config = {
      workspaceDir = "${workspaceDir}/${project.repoName}/${pkgs.lib.replaceStrings [ " " ] [ "_" ] job.name}";
      outputDir = "${outputDir}/v1/runs/${project.repoName}/${pkgs.lib.replaceStrings [ " " ] [ "_" ] job.name}";
      projectOutputDir = "${outputDir}/v1/runs/${project.repoName}";
    };
  };

  # 2. Serialize to JSON in Nix store
  jobSpecFile = pkgs.writeText "mjolnir-job-spec-${project.repoName}-${job.name}.json" (builtins.toJSON jobSpec);

  # Extract tool PATH and shellHook from devShell if provided
  shellInputs = if devShell != null then
    (devShell.nativeBuildInputs or []) ++
    (devShell.buildInputs or []) ++
    (devShell.propagatedBuildInputs or []) ++
    (if devShell ? outPath then [ devShell ] else [])
  else [];

  shellBinPath = pkgs.lib.makeBinPath shellInputs;
  shellHook = if devShell != null && devShell ? shellHook then devShell.shellHook else "";

  # 5. Assemble execution script
  launcher = pkgs.writeShellScriptBin "mjolnir-orchestrator-${project.repoName}-${pkgs.lib.replaceStrings [ " " ] [ "_" ] job.name}" ''
    set -e
    
    # Inject project-specific compiler tools into PATH
    ${pkgs.lib.optionalString (shellBinPath != "") ''
      export PATH="${shellBinPath}:$PATH"
    ''}

    ${pkgs.lib.optionalString (shellHook != "") ''
      ${shellHook}
    ''}

    exec ${mjolnir-app}/bin/mjolnir-run --spec "${jobSpecFile}" "$@"
  '';
in
  launcher
