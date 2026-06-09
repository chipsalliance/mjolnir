# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
{
  name,
  workspaceDir,
  outputDir,
  backend ? null,
  model ? null,
  numFiles ? 10,
  enableGcsUpload ? false,
  target ? null,
  agentDir ? ../../agents/rust_auditor,
  postExtract ? null,
  postTransform ? null,
}:
let
  defaultTarget = {
    repoUrl = "https://github.com/chipsalliance/caliptra-sw.git";
    repoName = "caliptra-sw";
    commit = "latest";
    fileCommand = "${pkgs.fd}/bin/fd -t f -e rs";
  };

  defaultPostExtract = ''
    echo "${name}: Update file list to only include first ${toString numFiles} Rust files..."
    cd "$CODE_DIR"
    ${pkgs.fd}/bin/fd -H -e rs . > "$ANALYSIS_FILES_FILE.tmp"
    head -n ${toString numFiles} "$ANALYSIS_FILES_FILE.tmp" > "$ANALYSIS_FILES_FILE"
    rm "$ANALYSIS_FILES_FILE.tmp"
    cd "$TOP_DIR"
  '';

  # Resolve the clean Target module directly
  resolvedTarget = import ../../nix/git/git.nix ({ inherit pkgs; } // (if target != null then target else defaultTarget));

  # Build simple local storage helper directly
  localStore = import ../../nix/storage/local.nix { inherit pkgs; path = outputDir; };
  gcsStore = import ../../nix/storage/gcs.nix { inherit pkgs; path = name; };

  storage = {
    name = if enableGcsUpload then "local+gcs" else "local";
    upload = { runDir }: ''
      ${localStore.upload { inherit runDir; }}
      ${if enableGcsUpload then gcsStore.upload { inherit runDir; } else ""}
    '';
  };

  # Resolved prompt (simple static wrapper using the raw backend name string)
  prompt = import ../../nix/orchestration/load.nix {
    inherit pkgs;
    inherit agentDir;
    backendName = backend;
  };

  # Map all backends for the orchestrator so it can look up the matching execution templates
  backendsList = {
    mock = import ../../nix/mock.nix { inherit pkgs; };
    gemini = import ../../nix/main.nix { inherit pkgs; };
  };

  defaultPostTransform = import ../../nix/orchestration/postprocess.nix {
    inherit pkgs name;
    backends = backendsList;
    backendName = backend;
  };
in
{
  config = {
    inherit workspaceDir outputDir;
  };
  parallel = 5;

  target = resolvedTarget;
  backends = backendsList;
  inherit backend;
  inherit model;
  inherit storage;
  inherit prompt;

  hooks = {
    postExtract = if postExtract != null then postExtract else defaultPostExtract;
    postTransform = if postTransform != null then postTransform else defaultPostTransform;
  };
}

