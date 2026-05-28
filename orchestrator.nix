# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  pkgs ? import <nixpkgs> { },
  jobFile ? ./jobs/test-job.nix,
  orchestratorCommit ? "unknown",
  isTest ? false,
}:

let
  # Define custom Python environment with needed dependencies
  myPython = pkgs.python3.withPackages (ps: [
    ps.pydantic
    ps.google-genai
  ]);

  # Merge evaluated job parameters with compiler-bound environment credentials
  jobExpr = import jobFile;
  # Inject custom python package into job's pkgs scope
  jobPkgs = pkgs // { python3 = myPython; };
  
  # Merge evaluated job parameters with compiler-bound environment credentials
  job = if builtins.isFunction jobExpr then jobExpr { pkgs = jobPkgs; } else jobExpr;


  # Fallback for hooks if missing entirely
  hooks = job.hooks or { };

  # Access configured backends and default backend name from job
  backends = job.backends;
  
  # Pre-computed framework configurations: check if the job statically binds these parameters
  defaultBackend = if job.backend != null then job.backend else null;
  defaultParallel = toString job.parallel;
  defaultModel = if job.model != null then job.model else null;

  # Generate run scripts for all available backends
  backendScripts = builtins.mapAttrs (name: backendModule:
    let
      runFunc = backendModule.runBatchAuditor;
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
    CHECKOUT_DIR=$(mktemp -d "$WORKSPACE_DIR/checkout_''${MJOLNIR_BACKEND}_${job.target.repoName}.XXXXXX")

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
    REPORT_FILE="$RUN_DIR/main_report.json"

    echo "Running threat analysis with backend: $MJOLNIR_BACKEND..."

    ${hooks.preReport or ""}
    cd "$TOP_DIR"

    # Execute the backend-specific script dynamically at runtime
    case "$MJOLNIR_BACKEND" in
      ${builtins.concatStringsSep "\n" (builtins.map (name: ''
        "${name}")
          ${backendScripts.${name}}
          ;;
      '') (builtins.attrNames backends))}
      *)
        echo "Error: Backend $MJOLNIR_BACKEND is not available in this build." >&2
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

    # -------------------------------------------------------------------------
    # Unified Environment & Parameter Resolution (Three-Tier Priority)
    # -------------------------------------------------------------------------
    # 1. Initialize defaults from Nix build-time configuration (if non-null)
    DEFAULT_BACKEND="${if defaultBackend != null then defaultBackend else ""}"
    DEFAULT_PARALLEL="${defaultParallel}"
    DEFAULT_MODEL="${if defaultModel != null then defaultModel else ""}"

    # 2. Parameter prioritization resolution:
    # - If the Nix job config actively defined a static production parameter (not empty and not mock), it takes HIGHEST priority (locks it).
    # - If this is a test run (isTest is true), we also lock it to the Nix defaults (even if they are "mock").
    # - Otherwise, dynamic profiles fallback to Environment overrides, and then CLI flags.
    if [ -n "$DEFAULT_BACKEND" ] && { [ "$DEFAULT_BACKEND" != "mock" ] || ${if isTest then "true" else "false"}; }; then
      MJOLNIR_BACKEND="$DEFAULT_BACKEND"
    else
      MJOLNIR_BACKEND="''${MJOLNIR_BACKEND:-}"
    fi

    if [ -n "$DEFAULT_MODEL" ] && { [ "$DEFAULT_MODEL" != "mock" ] || ${if isTest then "true" else "false"}; }; then
      MJOLNIR_MODEL="$DEFAULT_MODEL"
    else
      MJOLNIR_MODEL="''${MJOLNIR_MODEL:-}"
    fi

    # 3. Parse runtime CLI arguments (which override both Env and Nix)
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --backend)
          if [[ -n "$2" ]]; then
            MJOLNIR_BACKEND="$2"
            shift 2
          else
            echo "Error: --backend requires an argument" >&2
            exit 1
          fi
          ;;
        --parallel)
          if [[ -n "$2" && "$2" =~ ^[0-9]+$ ]]; then
            MJOLNIR_PARALLEL="$2"
            shift 2
          else
            echo "Error: --parallel requires a positive integer argument" >&2
            exit 1
          fi
          ;;
        --model)
          if [[ -n "$2" ]]; then
            MJOLNIR_MODEL="$2"
            shift 2
          else
            echo "Error: --model requires an argument" >&2
            exit 1
          fi
          ;;
        *)
          echo "Unknown argument: $1" >&2
          exit 1
          ;;
      esac
    done

    # Cleanly export whatever credentials are provided dynamically by the shell
    export GOOGLE_CLOUD_PROJECT="''${GOOGLE_CLOUD_PROJECT:-}"
    export GOOGLE_CLOUD_LOCATION="''${GOOGLE_CLOUD_LOCATION:-}"
    export GOOGLE_APPLICATION_CREDENTIALS="''${GOOGLE_APPLICATION_CREDENTIALS:-}"
    export GEMINI_API_KEY="''${GEMINI_API_KEY:-}"

    ${if isTest then "" else ''
      # Strict validation: Guarantee active parameters exist before letting production jobs execute
      if [ -z "$MJOLNIR_BACKEND" ] || [ "$MJOLNIR_BACKEND" = "mock" ]; then
        echo "Mjolnir Configuration Error: Invalid or missing target backend! You must define a valid production backend by passing the CLI argument '--backend <name>' or by exporting the environment variable 'MJOLNIR_BACKEND' (e.g., gemini)." >&2
        exit 1
      fi
      if [ -z "$MJOLNIR_MODEL" ] || [ "$MJOLNIR_MODEL" = "mock" ] || [ "$MJOLNIR_MODEL" = "unknown" ]; then
        echo "Mjolnir Configuration Error: Invalid or missing target model! You must define a valid production model by passing the CLI argument '--model <name>' or by exporting the environment variable 'MJOLNIR_MODEL' (e.g., gemini-3.5-flash)." >&2
        exit 1
      fi
    ''}

    # Export resolved configuration parameters under the unified prefix
    export MJOLNIR_BACKEND
    export MJOLNIR_PARALLEL="''${MJOLNIR_PARALLEL:-''${DEFAULT_PARALLEL:-1}}"
    export MJOLNIR_MODEL
    export MJOLNIR_GCS_BUCKET="''${MJOLNIR_GCS_BUCKET:-}"

    has_api_key=0
    has_vertex=0
    vertex_valid=0

    if [ -n "$GEMINI_API_KEY" ]; then
      has_api_key=1
    fi
    if [ -n "$GOOGLE_CLOUD_PROJECT" ] || [ -n "$GOOGLE_CLOUD_LOCATION" ] || [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
      has_vertex=1
    fi
    if [ -n "$GOOGLE_CLOUD_PROJECT" ] && [ -n "$GOOGLE_CLOUD_LOCATION" ] && [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
      vertex_valid=1
    fi

    if [ $has_api_key -eq 1 ] && [ $has_vertex -eq 1 ]; then
      echo "Mjolnir Configuration Error: Ambiguous configuration! Both GEMINI_API_KEY and Vertex AI parameters are defined. Please export only ONE credentials backend." >&2
      exit 1
    fi
    if [ $has_vertex -eq 1 ] && [ $vertex_valid -eq 0 ]; then
      echo "Mjolnir Configuration Error: Incomplete Vertex AI configuration! To use Vertex AI, you must export ALL 3 parameters: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, and GOOGLE_APPLICATION_CREDENTIALS." >&2
      exit 1
    fi

    TOP_DIR=$(pwd)
    START_TIME=$(date +%s)

    # Create unique output folder for all artifacts
    RUN_ID="''${MJOLNIR_BACKEND}_${job.target.repoName}_$(date +%Y%m%d_%H%M%S)"
    STORAGE_PATH="${job.config.outputDir}"
    RUN_DIR="$STORAGE_PATH/run_$RUN_ID"

    mkdir -p "$RUN_DIR"
    export VULN_RUN_DIR="$RUN_DIR"

    # Initialize metadata.json
    METADATA_FILE="$RUN_DIR/metadata.json"
    echo "Initializing metadata file at $METADATA_FILE..."
    echo "{" > "$METADATA_FILE"
    echo "  \"timestamp\": \"$(date -u +'%Y-%m-%dT%H:%M:%SZ')\"," >> "$METADATA_FILE"
    echo "  \"orchestrator_commit\": \"${orchestratorCommit}\"" >> "$METADATA_FILE"
    echo "}" >> "$METADATA_FILE"

    LOG_FILE="$RUN_DIR/execution_log.txt"

    run_job() {
      echo "=================================================="
      echo " Mjolnir: Environment Configuration Diagnostic"
      echo " - BACKEND: $MJOLNIR_BACKEND"
      echo " - MODEL: $MJOLNIR_MODEL"
      if [ -n "$MJOLNIR_GCS_BUCKET" ]; then
        echo " - GCS_BUCKET: $MJOLNIR_GCS_BUCKET"
      else
        echo " - GCS_BUCKET: [NOT CONFIGURED]"
      fi
      echo " - PARALLEL: $MJOLNIR_PARALLEL"
      if [ -n "$GOOGLE_CLOUD_PROJECT" ]; then echo " - GOOGLE_CLOUD_PROJECT: $GOOGLE_CLOUD_PROJECT"; fi
      if [ -n "$GOOGLE_CLOUD_LOCATION" ]; then echo " - GOOGLE_CLOUD_LOCATION: $GOOGLE_CLOUD_LOCATION"; fi
      if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]; then echo " - GOOGLE_APPLICATION_CREDENTIALS: $GOOGLE_APPLICATION_CREDENTIALS"; fi
      if [ -n "$GEMINI_API_KEY" ]; then echo " - GEMINI_API_KEY: [SECURE]"; fi
      echo "=================================================="

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
