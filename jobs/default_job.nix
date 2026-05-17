# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
{
  name,
  workspaceDir,
  outputDir,
  target,
  parallel ? 10,
  postExtract ? "",
  agentDir ? ../agents/rust_auditor,
  contextFile ? null,
  timeout ? null,
  backend ? "gemini", # Default backend name
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

  # Evaluate all backend functions with job-specific parameters
  evaluateBackend = name: backendFunc:
    let
      expectedArgs = builtins.functionArgs backendFunc;
      allArgs = {
        inherit pkgs;
        silentMissing = true;
        inherit parallel;
        inherit timeout;
      };
      filteredArgs = pkgs.lib.filterAttrs (argName: _: expectedArgs ? ${argName}) allArgs;
    in
      backendFunc filteredArgs;

  loadedBackends = builtins.mapAttrs evaluateBackend allBackendFuncs;

  dashboardGenerator = import ../backends/dashboard_generator/dashboard_generator.nix { inherit pkgs; };

  # Select backend
  resolvedBackend = if backend != null then backend else "gemini";

  # Load adversarial filtering prompt using chosen backend's name
  adversarialPrompt = import ../agents/load.nix {
    inherit pkgs;
    agentDir = ../agents/adversarial_reviewer;
    backendName = resolvedBackend;
  };

  # Filter backends that support runSingle
  singleRunBackends = pkgs.lib.filterAttrs (name: backendModule:
    backendModule ? runSingle
  ) loadedBackends;
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
    name = "local+gcs";
    upload = { runDir }: ''
      ${local.upload { inherit runDir; }}
      ${gcs.upload { inherit runDir; }}
    '';
  };

  # Backend Configuration
  backends = loadedBackends;
  backend = resolvedBackend;

  # Hooks
  hooks = {
    preExtract = ''
      echo "${name}: Before extraction"
    '';
    postExtract = ''
      export DEPENDENCY_GRAPH_FILE="$WORKSPACE_DIR/dependency_graph.toml"

      ${pkgs.python3}/bin/python3 ${../backends/extract_deps.py} \
          --src "$CODE_DIR" \
          --output "$DEPENDENCY_GRAPH_FILE" \
          --filter-list "$ANALYSIS_FILES_FILE"

      ${postExtract}
    '';
    postTransform = ''
      echo "${name}: Adversarial security review preparation..."

      # Final merged TOML
      REVIEWED_TOML="$VULN_RUN_DIR/reviewed_report.toml"

      # Create a target directory for the clusters
      CLUSTER_DIR="$VULN_RUN_DIR/clusters"
      mkdir -p "$CLUSTER_DIR"

      echo "${name}: Pre-sanitizing initial agent output..."
      CLEAN_REPORT_FILE="$VULN_RUN_DIR/clean_initial_report.toml"
      python3 ${../backends}/sanitize_report.py \
          --original "$REPORT_FILE" \
          --review /dev/null \
          --output "$CLEAN_REPORT_FILE"

      # Slice findings into context-bounded packages
      echo "${name}: Clustering phase 1 findings via graph analysis..."
      python3 ${../backends}/cluster_report.py \
          --report "$REPORT_FILE" \
          --deps "$DEPENDENCY_GRAPH_FILE" \
          --outdir "$CLUSTER_DIR" \
          --max-size 15

      # Execute phase 2 adversarial review 
      echo "${name}: Executing parallel adversarial reviews via native batch mode..."

      # Create a text file listing all the cluster files
      ls -1 "$CLUSTER_DIR" > "$VULN_RUN_DIR/cluster_list.txt"

      # The final aggregated output will go straight into raw_ai_review.txt
      RAW_REVIEW_TXT="$VULN_RUN_DIR/raw_ai_review.txt"

      # Run the backend from phase 1 for phase 2
      ${loadedBackends.${resolvedBackend}.run {
        systemPrompt = adversarialPrompt.backendArgs.systemPrompt;
        src = "$CLUSTER_DIR";
        files = "$VULN_RUN_DIR/cluster_list.txt";
        output = "$RAW_REVIEW_TXT";
      }}

      # Ensure the file exists even if 0 clusters were generated
      touch "$RAW_REVIEW_TXT"

      echo "${name}: Merging reviewed clusters into final report..."
      python3 ${../backends}/sanitize_report.py \
          --original "$CLEAN_REPORT_FILE" \
          --review "$RAW_REVIEW_TXT" \
          --output "$REVIEWED_TOML"

      echo "${name}: Generating Markdown report..."
      python3 ${../backends}/generate_markdown.py --input "$REVIEWED_TOML" --output "$VULN_RUN_DIR/reviewed_report.md"

      echo "${name}: Generating consolidated dashboard..."
      ${dashboardGenerator.run {
        src = "$REVIEWED_TOML";
        output = "$VULN_RUN_DIR/dashboard.html";
      }}
    '';
  };
}
