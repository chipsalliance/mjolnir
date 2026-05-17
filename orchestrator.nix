# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  pkgs ? import <nixpkgs> { },
  jobFile ? ./jobs/test-job.nix,
  orchestratorCommit ? "unknown",
}:

let
  jobExpr = import jobFile;
  job = if builtins.isFunction jobExpr then jobExpr { inherit pkgs; } else jobExpr;

  pythonEnv = pkgs.python3.withPackages (ps: with ps; [ networkx ]);

  # Fallback for hooks if missing entirely
  hooks = job.hooks or { };

  # Access configured backends and default backend name from job
  backends = job.backends;
  defaultBackendName = job.backend;

  # Generate run scripts for all available backends
  backendScripts = builtins.mapAttrs (name: backendModule:
    let
      runFunc = backendModule.run;
      expectedArgs = builtins.functionArgs runFunc;
      allArgs = job.prompt.backendArgs
        // {
          src = "$CODE_DIR";
          files = "$ANALYSIS_FILES_FILE";
          output = "$REPORT_FILE";
        };
      filteredArgs = pkgs.lib.filterAttrs (argName: _: expectedArgs ? ${argName}) allArgs;
    in
      runFunc filteredArgs
  ) backends;

  # ---------------------------------------------------------------------------
  # Phase Definitions
  # ---------------------------------------------------------------------------

  extractPhase = ''
    # -------------------------------------------------------------------------
    # Extract Phase
    # -------------------------------------------------------------------------
    echo "Running Extract Phase..."
    ${hooks.preExtract or ""}
    cd "$TOP_DIR"

    # Use the configured workspace directory
    WORKSPACE_DIR="${job.config.workspaceDir}"
    mkdir -p "$WORKSPACE_DIR"

    # Create a unique, named checkout directory within the workspace
    # Format: <backend_name>_<repo_name>_XXXXXX
    CHECKOUT_DIR=$(mktemp -d "$WORKSPACE_DIR/checkout_''${BACKEND}_${job.target.repoName}.XXXXXX")

    # Export it for use in hooks and backend
    export CODE_DIR="$CHECKOUT_DIR"

    # Execute the target-specific checkout script
    ${job.target.checkout { checkoutDir = "$CODE_DIR"; }}

    # Write target metadata
    ${job.target.writeMetadata { checkoutDir = "$CODE_DIR"; metadataFile = "$METADATA_FILE"; }}

    # Create the analysis files list
    export ANALYSIS_FILES_FILE=$(mktemp "$WORKSPACE_DIR/analysis_files.XXXXXX")
    ${job.target.findFiles {
      checkoutDir = "$CODE_DIR";
      output = "$ANALYSIS_FILES_FILE";
    }}

    cd "$TOP_DIR"
    ${hooks.postExtract or ""}
    cd "$TOP_DIR"
  '';

  transformPhase = ''
    # -------------------------------------------------------------------------
    # Transform Phase
    # -------------------------------------------------------------------------
    echo "Running Transform Phase..."
    ${hooks.preTransform or ""}
    cd "$TOP_DIR"

    # Set main report file in the run dir
    REPORT_FILE="$RUN_DIR/main_report.toml"

    echo "Running threat analysis with backend: $BACKEND..."

    ${hooks.preReport or ""}
    cd "$TOP_DIR"

    # Execute the backend-specific script dynamically at runtime
    case "$BACKEND" in
      ${builtins.concatStringsSep "\n" (builtins.map (name: ''
        "${name}")
          ${backendScripts.${name}}
          ;;
      '') (builtins.attrNames backends))}
      *)
        echo "Error: Backend $BACKEND is not available in this build." >&2
        exit 1
        ;;
    esac

    cd "$TOP_DIR"
    ${hooks.postReport or ""}
    cd "$TOP_DIR"
    ${hooks.postTransform or ""}
    cd "$TOP_DIR"
  '';

  loadPhase = ''
    # -------------------------------------------------------------------------
    # Load Phase
    # -------------------------------------------------------------------------
    echo "Running Load Phase..."
    ${hooks.preLoad or ""}
    cd "$TOP_DIR"

    echo "Handling results with storage backend: ${job.storage.name or "unknown"}..."

    # Execute the storage-specific upload script
    ${job.storage.upload { runDir = "$RUN_DIR"; }}

    cd "$TOP_DIR"
    ${hooks.postLoad or ""}
    cd "$TOP_DIR"
  '';

  # Generate the main script
  vuln-orchestrator = pkgs.writeShellScriptBin "vuln-orchestrator" ''
    set -e
    set -o pipefail

    # Initialize default parallel from Nix job config
    PARALLEL="${toString job.parallel}"

    # Parse runtime arguments
    BACKEND="${defaultBackendName}"
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --backend)
          if [[ -n "$2" ]]; then
            BACKEND="$2"
            shift 2
          else
            echo "Error: --backend requires an argument" >&2
            exit 1
          fi
          ;;
        --parallel)
          if [[ -n "$2" && "$2" =~ ^[0-9]+$ ]]; then
            PARALLEL="$2"
            shift 2
          else
            echo "Error: --parallel requires a positive integer argument" >&2
            exit 1
          fi
          ;;
        *)
          echo "Unknown argument: $1" >&2
          exit 1
          ;;
      esac
    done
    export BACKEND

    TOP_DIR=$(pwd)
    START_TIME=$(date +%s)

    export PATH="${pythonEnv}/bin:$PATH"

    # Create unique output folder for all artifacts
    RUN_ID="''${BACKEND}_${job.target.repoName}_$(date +%Y%m%d_%H%M%S)"
    STORAGE_PATH="${job.config.outputDir}"
    RUN_DIR="$STORAGE_PATH/run_$RUN_ID"

    mkdir -p "$RUN_DIR"
    export VULN_RUN_DIR="$RUN_DIR"

    # Initialize metadata.toml
    METADATA_FILE="$RUN_DIR/metadata.toml"
    echo "Initializing metadata file at $METADATA_FILE..."
    echo "timestamp = \"$(date -u +'%Y-%m-%dT%H:%M:%SZ')\"" > "$METADATA_FILE"
    echo "orchestrator_commit = \"${orchestratorCommit}\"" >> "$METADATA_FILE"

    LOG_FILE="$RUN_DIR/execution_log.txt"

    run_job() {
      echo "Starting threat analysis job..."

      ${extractPhase}
      ${transformPhase}
      ${loadPhase}

      END_TIME=$(date +%s)
      ELAPSED_TIME=$((END_TIME - START_TIME))

      # Workspace and analysis files are preserved for inspection in:
      # $CODE_DIR
      # $ANALYSIS_FILES_FILE

      echo "Threat analysis job complete."
      echo "Results saved in: $RUN_DIR"
      echo "Workspace preserved in: $CODE_DIR"
      echo "Total E2E Wall Time: ''${ELAPSED_TIME}s"
    }

    run_job 2>&1 | tee "$LOG_FILE"
  '';

in
vuln-orchestrator
