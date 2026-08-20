<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Mjolnir Integration Guide

This guide describes how to integrate Mjolnir into software repositories for automated AI-driven security auditing, continuous PR diff scanning, and centralized artifact export using a **Local-First, Decentralized** architecture.

---

## 1. Architecture Overview

Mjolnir operates as a **reusable security auditing tool and Nix flake library**:

- **Decentralized Repository Ownership**: Target repositories maintain their own `./mjolnir/` configuration directory containing project metadata (`project.nix`), threat models (`threat_model.md`), and job definitions (`jobs/*.nix`).
- **Autodiscovered Nix Jobs**: Target repositories import `mjolnir.lib.discoverProjectJobs` in their `flake.nix`, automatically exposing each job as a native runnable Nix package (`nix run .#ci`, `nix run .#main`, etc.).
- **Language-Agnostic Local Execution**: Developers run audits directly via `nix run .#<job>`, reproducing exact CI behavior locally across any project language (Rust, C, Go, SystemVerilog).
- **Self-Contained Outputs**: Local runs output structured audit artifacts to `./test-out/results/` (or your configured `outputDir`).

---

## 2. Integrating Mjolnir into Repository X

### Step 1: Create the `./mjolnir/` Directory

In your repository, create the `./mjolnir/` configuration directory (note: while this directory is typically placed at `./mjolnir/`, it can be located anywhere in your repository):

```text
your-repo/
├── mjolnir/
│   ├── project.nix          # Project metadata, extensions, and threat model
│   ├── threat_model.md      # Authoritative threat model for the repository
│   └── jobs/
│       ├── local.nix        # Local working tree audit profile
│       ├── ci.nix           # PR diff audit job profile
│       └── main.nix         # Full repository audit job profile
```

#### `mjolnir/project.nix`

```nix
# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "Your Project Name";
  repoName = "your-repo";
  repoUrl = "https://github.com/org/your-repo.git";
  threatModel = ./threat_model.md;
  outputDir = "./test-out/results";
  workspaceDir = "./test-out/workspace";

  defaultModel = "gemini-3.6-flash";
  defaultProvider = "adk";
  defaultBatchSize = 64;
  defaultExtensions = [ "rs" "c" "h" "go" "sv" "py" ];
}
```

#### `mjolnir/jobs/local.nix`

```nix
# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "Local";
  localDir = ".";
  srcDirs = [ "." ];
}
```

#### `tools/mjolnir/jobs/ci.nix`

```nix
# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "CI";
  localDir = ".";
  srcDirs = [ "." ];
}
```

#### `mjolnir/jobs/main.nix`

```nix
# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  name = "Main";
  branch = "main";
  srcDirs = [ "." ];
}
```

---

### Step 2: Add Mjolnir to `flake.nix`

In your repository's `flake.nix`, add Mjolnir as an input and use `mjolnir.lib.discoverProjectJobs`:

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    mjolnir = {
      url = "github:chipsalliance/mjolnir";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, mjolnir, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        # Optional: custom devShell/toolchain for the repository
        devShell = pkgs.mkShell {
          nativeBuildInputs = with pkgs; [ ... ];
        };
      in
      {
        devShells.default = devShell;

        packages = mjolnir.lib.discoverProjectJobs {
          inherit pkgs devShell;
          mjolnirApp = mjolnir.packages.${system}.mjolnir-app;
          projectDir = ./tools/mjolnir;
          deployPackages = {
            inherit (mjolnir.packages.${system}) deploy-gcs-runs;
          };
        };
      }
    );

}
```

---

### Step 3: Run Audits Locally

Any job defined in your configuration directory (`jobs/`) is immediately runnable via Nix:

```bash
# Run PR diff audit against main:
nix run .#ci -- --diff-base main --diff-head HEAD

# Run full repository audit:
nix run .#main

# Sync audit artifacts to a Google Cloud Storage bucket:
nix run .#deploy-gcs-runs -- --bucket my-reports-bucket --output-dir ./test-out/results
```

---

### Step 4: Add PR Audit CI Workflow (`.github/workflows/mjolnir_audit.yml`)

Add an automated CI workflow in `.github/workflows/mjolnir_audit.yml` to audit incoming pull requests and sync artifacts:

```yaml
name: Mjolnir Security Audit (PR)

on:
  pull_request:
    branches:
      - main

permissions:
  contents: read

jobs:
  mjolnir-audit:
    name: Mjolnir Security Audit (PR)
    runs-on: e2-standard-2-AI
    timeout-minutes: 30

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Install Nix
        run: |
          sh <(curl -L https://nixos.org/nix/install) --no-daemon
          . ~/.nix-profile/etc/profile.d/nix.sh
          mkdir -p ~/.config/nix
          echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf
          echo "$HOME/.nix-profile/bin" >> $GITHUB_PATH

      - name: Run Mjolnir Security Audit
        run: |
          nix run path:.#ci -- \
            --diff-base "${{ github.event.pull_request.base.sha }}" \
            --diff-head "${{ github.event.pull_request.head.sha }}" \
            --pr "${{ github.event.pull_request.html_url }}" \
            --trigger ci

      - name: Sync Audit Artifacts to GCS
        run: |
          nix run path:.#deploy-gcs-runs -- \
            --bucket "caliptra-github-ci-caliptra-reports" \
            --output-dir "./test-out/results"
```

---

### Step 5: Update `.gitignore`

Add Mjolnir's local results and workspace directories to your `.gitignore`:

```gitignore
# Mjolnir Scan Output and Workspaces
test-out/
workspace/
output/
```

---

## 3. Deployment Commands & Storage Layout

Mjolnir provides data deployment via Nix:

1. **`deploy-gcs-runs`** (Data Deployment):
   - **Purpose**: Syncs versioned audit scan runs from `--output-dir` (e.g. `./test-out/results`) into `gs://<bucket>/v1/runs/`.
   - **Usage**: `nix run .#deploy-gcs-runs -- --bucket <BUCKET> --output-dir ./test-out/results`

2. **`deploy-gcs-web`** (UI Deployment):
   - **Purpose**: Uploads the bundled WASM Web Dashboard assets directly to the bucket root.
   - **Usage**: `nix run .#deploy-gcs-web -- --bucket <BUCKET>`

### Bucket Layout & Dynamic Run Discovery

The Google Cloud Storage bucket uses a standardized, versioned layout where the Web Dashboard automatically discovers all scan runs via the `v1/runs/` prefix:

```text
gs://<bucket>/
├── index.html                               # Web dashboard entry point
├── web/                                     # Static & compiled WASM bundle assets
│   ├── constants.js                         # API_VERSION, RUNS_SUBDIR, WEB_SUBDIR
│   ├── app.js                               # Dashboard frontend runtime
│   ├── style.css
│   ├── wasm-worker.js
│   └── dist/
│       ├── mjolnir_dashboard_wasm.js
│       └── mjolnir_dashboard_wasm_bg.wasm
└── v1/
    └── runs/                                # Versioned scan runs (RUNS_SUBDIR)
        └── <project>/
            └── <job>/
                └── run_<timestamp>/
                    ├── job.log
                    ├── metadata.json
                    ├── vulnerabilities.json
                    ├── token_usage.json
                    └── tool_usage.json
```

---

## 4. Environment & Credentials Configuration

- **Local Developer Workstations**:
  - Set `GEMINI_API_KEY=<your-key>` in your environment, OR
  - Run `gcloud auth application-default login` for Vertex AI ADC access.

---

## 5. Export Artifacts & Outputs

For every analysis run, Mjolnir exports structured audit artifacts under `<outputDir>/v1/runs/<repo>/<job>/run_<timestamp>/` (e.g. `./test-out/results/v1/runs/<repo>/<job>/run_<timestamp>/`):

| Artifact                       | Description                                                                                               |
| :----------------------------- | :-------------------------------------------------------------------------------------------------------- |
| `vulnerabilities.json`         | Complete audit graph containing all discovered vulnerabilities, historical findings, and agent reasoning. |
| `vulnerabilities_minimal.json` | Filtered subset containing only active, verified `Status.OPEN` vulnerabilities.                           |
| `metadata.json`                | Run metadata including execution timestamp, commit SHA, model, provider, and status.                      |
| `job.log`                      | Raw execution log and turn telemetry.                                                                     |
| `token_usage.json`             | LLM token consumption breakdown.                                                                          |
| `tool_usage.json`              | Detailed agent tool call logs and invocation stats.                                                       |
