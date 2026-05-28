# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
{
  name,
  workspaceDir,
  outputDir,
  target,
  parallel ? null,
  postExtract ? "",
  agentDir,
  contextFile ? null,
  timeout ? null,
  backend ? null,
  model ? null,
  enableGcsUpload ? true,
}:
let
  # Dynamic Backend Loading
  localBackendsDir = ../backends;

  safeReadDir = path:
    if builtins.pathExists path
    then builtins.readDir path
    else {};

  localBackends = safeReadDir localBackendsDir;

  # Helper to identify valid backends and their paths from the directory listing
  getBackendPath = name: type:
    if type == "directory" then
      let path = localBackendsDir + "/${name}/${name}.nix";
      in if builtins.pathExists path then { inherit name path; } else null
    else if type == "regular" && pkgs.lib.hasSuffix ".nix" name then
      let
        backendName = pkgs.lib.removeSuffix ".nix" name;
        path = localBackendsDir + "/${name}";
      in { name = backendName; inherit path; }
    else null;

  backendAttrsList = pkgs.lib.mapAttrsToList getBackendPath localBackends;
  validBackends = builtins.filter (x: x != null) backendAttrsList;

  openSourceBackendFuncs = builtins.listToAttrs (builtins.map (x: {
    name = x.name;
    value = import x.path;
  }) validBackends);

  # Merge open-source backends with private backends injected via pkgs
  allBackendFuncs = openSourceBackendFuncs // (pkgs.privateBackends or {});

  # Evaluate all backend functions with static job parameters
  evaluateBackend = name: backendFunc:
    let
      expectedArgs = builtins.functionArgs backendFunc;
      allArgs = {
        inherit pkgs;
        silentMissing = true;
      };
      filteredArgs = pkgs.lib.filterAttrs (argName: _: expectedArgs ? ${argName}) allArgs;
    in
      backendFunc filteredArgs;

  loadedBackends = builtins.mapAttrs evaluateBackend allBackendFuncs;

  # Select backend
  resolvedBackend = if backend != null then backend else "mock";

in
{
  config = {
    inherit workspaceDir outputDir;
  };
  inherit parallel;

  target = import ../target/git.nix ({ inherit pkgs; } // target);

  # Load prompt
  prompt = import ../agents/load.nix {
    inherit pkgs;
    inherit agentDir;
    backendName = resolvedBackend;
    inherit contextFile;
  };

  # Storage Configuration
  storage = let
    local = import ../storage/local.nix { inherit pkgs; path = outputDir; };
    gcs = import ../storage/gcs.nix { inherit pkgs; path = name; };
  in {
    name = if enableGcsUpload then "local+gcs" else "local";
    upload = { runDir }: ''
      ${local.upload { inherit runDir; }}
      ${if enableGcsUpload then gcs.upload { inherit runDir; } else ""}
    '';
  };

  # Backend Configuration
  backends = loadedBackends;
  backend = resolvedBackend;
  inherit model;

  # Hooks
  hooks = {
    preExtract = ''
      echo "${name}: Before extraction"
    '';
    inherit postExtract;
    postTransform = import ./postprocess.nix {
      inherit pkgs name;
      backends = loadedBackends;
      backendName = resolvedBackend;
    };
  };
}
