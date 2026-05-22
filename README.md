# Mjolnir: AI Security Analysis Infrastructure

This repository contains the configuration, specialized agent definitions, and
infrastructure for **Mjolnir**, an AI driven security auditing framework
designed for open-source Root-of-Trust (RoT) projects like Caliptra, OpenTitan,
and OpenPRoT.

Mjolnir leverages advanced AI foundation models and adversarial
review pipelines to provide continuous security assurance through periodic,
incremental scanning of firmware and RTL.

Mjolnir is built using Nix to facilitate reproducibility, flexibility, and ease of deployment in CI environments.

## Architecture

### Phases

Mjolnir performs its analyses in phases, described below.

1.  **Extract**: The tool prepares a unique checkout directory within your workspace and uses the **Target** component to clone and checkout the code.
2.  **Transform**: It prepares the **Prompts** and executes the **Backend** model. The backend model analyzes the code in the checkout directory and writes a report to a unique, timestamped run directory.
3.  **Load**: It delegates the results handling to the **Storage** backend, which may move or upload the entire run directory.

### Infrastructure Concepts

The Mjolnir infrastructure consists of the follow components:

- **Job Files (`jobs/*.nix`)**: Pure Nix files that assemble a specific run by plugging in Target, Backend, Prompt, Storage, and Hooks.
- **Targets (`target/*.nix`)**: Modules that define how to retrieve source code (e.g., `git.nix`).
- **Backends (`backends/*.nix`)**: Modules that describe how to run a specific AI model or analysis tool. (Note: `claude.nix` is currently a placeholder and not yet working).
- **Prompts (`prompts/*.nix`)**: Modules that handle the resolution and preparation of instructions and context to feed the backend model.
- **Storage Backends (`storage/*.nix`)**: Modules that define how to persist or upload the final run artifacts.
- **Hooks**: Bash script snippets that can be injected at various stages (e.g., `preExtract`, `postTransform`) to customize behavior (e.g., deleting files, running linters).

Below we elaborate on the interfaces to some of the key components described above.

### Target Component

Targets are responsible for retrieving the code to be analyzed.

- **Factory Function**: `{ pkgs, ... } -> { ... }`
- **Attributes**:
  - `repoName`: String, used for directory naming.
  - `checkout { checkoutDir }`: Returns a Bash snippet to clone/checkout the code into the provided directory.

### Backend Component

Backends are typically LLMs that perform the actual security analyses.

- **Factory Function**: `{ pkgs, ... } -> { ... }`
- **Attributes**:
  - `name`: String, used for naming run artifacts.
  - `run { systemPrompt, src, output }`: Returns a Bash snippet.
    - `systemPrompt`: Path to a file with the system instruction.
    - `src`: Path to the directory containing the source code.
    - `output`: Path where the agent should write its report.
- **Runtime Environment Overrides** (for Gemini):
  - `GOOGLE_CLOUD_PROJECT`: Overrides the default GCP Project ID used for Vertex AI API billing.
  - `PARALLEL`: Overrides the default number of parallel threads used during batch file processing.

### Prompts Component

The Prompts component prepares text and context to prime the backend models to perform their analyses.

- **Factory Function**: `{ pkgs, systemPrompt } -> { ... }`
- **Attributes**:
  - `backendArgs`: An attribute set containing pre-processed Nix store paths for `systemPrompt`.

### Storage Component

The Storage component handles the outputs of the backend component, e.g. the vulnerability reports produced by the LLM.

- **Factory Function**: `{ pkgs, ... } -> { ... }`
- **Attributes**:
  - `name`: String, for logging purposes.
  - `upload { runDir }`: Returns a Bash snippet to handle the results in the provided directory.
- **Runtime Environment Overrides** (for GCS):
  - `GCSDEST`: Completely overrides the destination Google Cloud Storage URI (e.g., `gs://my-custom-bucket/path/`).

---

## Getting Started

The tool uses Nix Flakes. Ensure you have Nix installed with flakes enabled.

### Running Audits

Audits are executed using `nix run .#<target>`. You can run individual component scans, predefined job groups, or test targets.

#### A. Standard Component Scans

These targets clone the respective repository, filter for relevant source files, perform per-file analysis using the Gemini backend, and generate a reviewed report and interactive dashboard.

- **Caliptra SW 2.1 Audit**: Filters for Rust files in ROM and Runtime.

  ```bash
  nix run .#caliptra-sw-2p1-latest
  ```

  _This job is configured to clone `chipsalliance/caliptra-sw`, filter for `.rs` files in `rom/dev/src` and `runtime/src`, and analyze them._

- **Caliptra MCU SW 2.0 Audit**:

  ```bash
  nix run .#caliptra-mcu-sw-2p0-latest
  ```

- **OpenTitan SW Subjob Audits**:
  Individual scans targeting specific components of OpenTitan software.
  ```bash
  nix run .#opentitan-rom
  nix run .#opentitan-rom-ext
  nix run .#opentitan-manuf
  nix run .#opentitan-lib
  nix run .#opentitan-crypto
  ```

#### B. Job Groups (Batch Scanning)

Job groups allow executing multiple audits sequentially. This is useful for full regressions or CI environments.

- **`scan-all`**: Runs all main component scans sequentially (`caliptra-sw-2p1-latest`, `caliptra-mcu-sw-2p0-latest`, and all 4 `opentitan` subjobs).
  ```bash
  nix run .#scan-all
  ```
- **`opentitan-all`**: Runs all 4 OpenTitan subjobs sequentially.
  ```bash
  nix run .#opentitan-all
  ```
- **`caliptra-all`**: Runs all Caliptra subjobs sequentially.
  ```bash
  nix run .#caliptra-all
  ```
- **`scan-all-test`**: Runs test/smoke scans (`smoke-test`).
  ```bash
  nix run .#scan-all-test
  ```

#### C. Test Targets

Used for verifying the infrastructure and authentication.

- **`smoke-test`**: Runs a quick analysis using a mock backend.
  ```bash
  nix run .#smoke-test
  ```

### Aggregating Scan Results

Mjolnir includes a script to aggregate vulnerability scan results from multiple
codebase scans into a centralized, interactive HTML dashboard. This is useful
for getting a high-level overview of all security audits.

The script looks for the latest scan results for the following components
(expected to be present in the repository root):

- **Caliptra MCU SW 2.0** (source: `output/caliptra/mcu-sw-2p0`)
- **Caliptra SW 2.1** (source: `output/caliptra/sw-2p1`)
- **OpenTitan ROM** (source: `output/opentitan/rom`)
- **OpenTitan ROM EXT** (source: `output/opentitan/rom_ext`)
- **OpenTitan Manuf** (source: `output/opentitan/manuf`)
- **OpenTitan Lib** (source: `output/opentitan/lib`)
- **OpenTitan Crypto** (source: `output/opentitan/crypto`)

#### Usage

To aggregate the results, run the `aggregate_results.py` script, providing a
target directory where the aggregated dashboard should be generated. By default,
it will use the `components.toml` configuration file located in the scripts directory:

```bash
python3 scripts/aggregate_results.py <target_dir> [options]
```

#### Options

- `--components <file>`: Path to TOML file containing component definitions. Can be specified multiple times to merge different configurations.
- `--regen-html`: Only regenerate the `index.html` landing page from existing
  results in the target directory, without copying new files.
- `-j`, `--jobs <job1> ...`: Aggregate the specified job and regenerate the
  `index.html` landing page.

#### Output Structure

The script will create the target directory and generate the following:

- `<target_dir>/index.html`: The main landing page dashboard linking to all
  component reports.
- `<target_dir>/<component_key>/`: Subdirectories for each component
  containing:
  - `dashboard.html`: The interactive HTML dashboard for that specific
    component scan.
  - `main_report.toml` / `main_report.md`: The full vulnerability report.
  - `reviewed_report.md`: The agent-filtered vulnerability report in
    Markdown.

The generated `index.html` uses a shared dark theme styling and provides quick
access to both HTML dashboards and Markdown reports.

---

### Aggregating Results from GCS

Mjolnir also includes a script to aggregate results directly from a GCS bucket without downloading them. This script scans the bucket for the latest results of each component and generates an `index.html` dashboard with links pointing directly to the objects in GCS.

#### Usage

To aggregate results from GCS, run the `aggregate_gcs_results.py` script:

```bash
python3 scripts/aggregate_gcs_results.py --bucket <bucket_name> [options]
```

#### Options

- `--bucket <name>`: (Required) The name of the GCS bucket.
- `--prefix <prefix>`: The prefix in the bucket where reports are stored (default: `v0`).
- `--components <file>`: Path to the TOML file containing component definitions. Defaults to `gcs_components.toml` in the script directory.
- `--output <file>`: The name of the generated HTML file (default: `index.html`).
- `--upload`: Automatically upload the generated `index.html` to the root of the specified GCS bucket.

#### Output

The script generates a single HTML file (default: `index.html`) containing the dashboard. If the `--upload` flag is used, it will be uploaded to `gs://<bucket_name>/index.html` and the public URL will be printed.

---

## Assembling a New Job

There are two ways to assemble a new auditing job:

### A. Using the Shared Job Builder (Recommended for Standard Audits)

For standard threat analysis audits that use the default agents and backends, you can use the shared job builder in `jobs/default_job.nix` to create a concise job definition:

```nix
{ pkgs }:
import ./default_job.nix { inherit pkgs; } {
  name = "My Custom Job";
  workspaceDir = "/tmp/my-workspace";
  outputDir = "./my-results";
  parallel = 50;

  target = {
    repoUrl = "https://github.com/example/repo.git";
    repoName = "my-repo";
    commit = "latest";
    fileCommand = "${pkgs.fd}/bin/fd -t f -e rs";
  };

  postExtract = ''
    echo "Custom cleanup logic after code extraction goes here..."
  '';
}
```

### B. Manual Component Assembly (For Advanced Use Cases)

If you need a custom workflow, different backend, or multiple custom hooks, create a file in `jobs/my-audit.nix`:

```nix
{ pkgs }:
let
  # 1. Initialize Components
  gitTarget = import ../target/git.nix {
    inherit pkgs;
    repoUrl = "https://github.com/example/repo.git";
    repoName = "my-project";
    commit = "latest";
  };

  prompt = import ../agents/load.nix {
    inherit pkgs;
    agentDir = ../agents/rust_auditor;
    backendName = geminiBackend.name;
  };

  geminiBackend = import ../backends/gemini.nix { inherit pkgs; };

  localStorage = import ../storage/local.nix {
    inherit pkgs;
    path = "../audits";
  };
in
{
  # 2. General Configuration
  config = {
    workspaceDir = "/tmp/audit-workspace";
    outputDir = "./results";
  };

  # 3. Component Assembly
  target = gitTarget;
  backend = geminiBackend;
  prompt = prompt;
  storage = localStorage;

  # 4. Custom Hooks (Optional)
  hooks = {
    postExtract = ''
      echo "Cleaning up non-source files with Python..."
      ${pkgs.python3}/bin/python3 <<EOF
import os
code_dir = os.environ.get('CODE_DIR')
for root, dirs, files in os.walk(code_dir):
    for file in files:
        if not file.endswith('.c'):
            os.remove(os.path.join(root, file))
EOF
    '';
  };
}
```

---

## Authentication & Operation Modes

Mjolnir uses **Application Default Credentials (ADC)** to authenticate with Google Cloud Vertex AI:

1.  **Install gcloud**: Ensure you have the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) installed.
2.  **Login**: Run the following command on your host machine to generate ADC:
    ```bash
    gcloud auth application-default login
    ```
3.  **Project ID**: Ensure your job configuration (or standard environment) specifies the correct billing GCP project.

The orchestrator will look for the credentials file at the standard location:
`$HOME/.config/gcloud/application_default_credentials.json`

## Testing

To verify the Nix infrastructure builds:

```
nix build .#smoke-test --no-link
```

To verify the tool with mocks:

```bash
nix run .#smoke-test
```

Results will be in the `test-output/smoke-test` directory.
