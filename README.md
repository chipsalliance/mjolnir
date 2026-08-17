<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Mjolnir

Mjolnir is an AI-driven security auditing framework designed for open-source Root-of-Trust (RoT) projects.

It leverages AI foundation models and adversarial review pipelines to provide continuous security assurance through periodic, incremental scanning of firmware and RTL.

## Pipeline Architecture

Mjolnir separates the declarative configuration and environment definition (Nix) from the imperative analysis execution (Python application engine).

```mermaid
graph TD
    subgraph Nix Layer [Nix Orchestration]
        A[projects/ directory] -->|1. Auto-discover| B(discovery.nix)
        B --> C[flake.nix targets]
        C -->|nix run .#job| D(orchestrator.nix)
        D -->|2. Generate| E[Job Spec JSON]
        D -->|3. Generate| F[Launcher Script]
    end

    subgraph Python Layer [Application Engine]
        F -->|4. Execute| G(main.py)
        E -.->|Reads configuration| G
        G --> H[Checkout target repo]
        H --> I[Discover source files]

        %% Parallel File Analysis
        I --> J1(Analysis Provider: File 1)
        I --> J2(Analysis Provider: File 2)
        I --> J3(Analysis Provider: File N)

        J1 --> M[vulnerabilities.json]
        J2 --> M
        J3 --> M

        M --> N[HTML Dashboard Generator]
        N --> O[Local/GCS Output]
    end
```

### Key Layers

- **Nix Layer (Orchestration)**:
  - **Discovery (`discovery.nix`)**: Scans the `projects/` directory to automatically register every project and job configuration as a Nix package target.
  - **Orchestration (`orchestrator.nix`)**: When a target is executed (via `nix run`), it packages the job by serializing the configuration attributes into a static JSON spec file in the Nix store, and builds a launcher script.
- **Python Layer (Application Engine)**:
  - **Orchestrator (`main.py`)**: Parses the serialized JSON spec, sets up the workspace directory, clones the target repository, and checks out the designated revision.
  - **Analysis Execution**: Filters files based on source directories and extensions, then delegates analysis to the specified provider backend (e.g., `genai` or `mock`).
  - **Reporting & Dashboarding**: Compiles the findings into `vulnerabilities.json` and generates an interactive HTML dashboard in the output directory.

### Execution Flow

1.  **Nix Auto-Discovery**: Nix dynamically generates packages from the `projects/` directory targets.
2.  **Target Launch**: Running `nix run .#<job-name>` executes the Nix-generated wrapper script.
3.  **JSON Spec Materialization**: The launcher script runs the application engine, passing a path to the serialized JSON job specification.
4.  **Checkout & Discovery**: Python clones/updates the target repository and identifies files matching the job's scope.
5.  **Scan Execution**: The chosen provider executes analysis on the source files and compiles the results.
6.  **Dashboard Generation**: The run's raw findings are compiled into reports and a local HTML dashboard.

## Directory Structure

- **[INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md)**: Guide for integrating Mjolnir security audits into repositories (GitHub Actions, GCS export, PR diff mode).
- **[app/mjolnir/](./app/mjolnir/)**: Core Python application engine, including agent tools, data models, and providers (mock, genai). See [Application Engine README](./app/mjolnir/README.md).
- **[nix/](./nix/)**: Nix infrastructure for job packaging, auto-discovery, and orchestration. See [Nix README](./nix/README.md).
- **[projects/](./projects/)**: Supported project definitions and job configurations. See [Projects README](./projects/README.md).
- **`output/`**: Generated analysis reports, run logs, and HTML dashboards.

## Supported Projects

All project definitions, job configurations, and nix setups are located under [projects/](./projects/). See the [Projects README](./projects/README.md) for more details on how to register new targets, or read the [Integration Guide](./INTEGRATION_GUIDE.md) for step-by-step onboarding instructions.

## Getting Started

Mjolnir requires Nix with flakes enabled.

### Running an Audit

To run a predefined project audit runner target, execute `nix run`:

```bash
nix run .#<project-runner-target>
```

#### Examples

- **Run Caliptra SW Mock E2E Audit**:
  ```bash
  nix run .#caliptra-sw-runner-test
  ```
- **Run OpenTitan ROM Audit**:
  ```bash
  nix run .#opentitan-rom
  ```

---

## WebAssembly Dashboard & Local Viewer

Mjolnir features a WebAssembly (WASM) dashboard for browsing security audit runs, filtering findings, and visualizing vulnerability flow telemetry.

### Launching Local Web Viewer

To compile the WASM engine and start the local development server (default: `http://localhost:8080`):

```bash
nix run .#web-viewer
```

### Deploying Dashboard & Runs to GCS

Deploy static WebAssembly dashboard assets to Google Cloud Storage:

```bash
nix run .#deploy-gcs-web
```

Sync local analysis runs from `output/v1/runs/` to Google Cloud Storage (test project runs are excluded by default):

```bash
nix run .#deploy-gcs-runs
```

Optional flags for run deployment:

- `--include-tests`: Include test and mock benchmark runs.

```bash
nix run .#deploy-gcs-runs -- --include-tests
```

---

## Authentication

Mjolnir uses **Application Default Credentials (ADC)** with **Google Cloud Vertex AI** by default, requiring **zero environment variables or secrets** in production.

### Vertex AI (Production & Local Development with ADC)

- **In Production (GCP / Compute Engine / GKE):**
  Authentication and GCP Project ID resolution are completely automatic via Application Default Credentials (ADC) and the Instance Metadata Server. No environment variables or credentials files are needed.

- **On Local Development Workstations:**
  Authenticate once with `gcloud`:
  ```bash
  gcloud auth application-default login
  gcloud config set project your-gcp-project-id
  ```
  Mjolnir auto-discovers your credentials and project with zero configuration required.

### Gemini API Key (Optional / Non-GCP Fallback)

If running outside Google Cloud without ADC, you can optionally set a Gemini Developer API key:

```bash
export GEMINI_API_KEY="AIzaSy..."
```

---

## Testing

Mjolnir includes a suite of test targets to verify local pipelines, GCS uploads, and live LLM integration.

### Verification of Nix Infrastructure (Mocks)

To verify that the Nix derivations build cleanly:

```bash
nix build .#mock-smoke-test --no-link
```

To run a local mock test (verifies the python runner and local file system hooks):

```bash
nix run .#mock-smoke-test
```

### Live LLM Testing

Run live scans on test fixtures using ambient ADC or optional API key:

```bash
# Option A: GenAI Provider Target
nix run .#genai-gemini-test

# Option B: ADK Provider Target (Google Agent Development Kit)
nix run .#adk-gemini-test

# Option C: ADK Ingestion Mode
nix run .#adk-gemini-ingest-test
```

### Running All Tests

To run all mock and live tests in a single command:

```bash
nix run .#test-all
```

To test the project runners (firmware compilation verification) locally:

```bash
nix run .#test-all-runners
```
