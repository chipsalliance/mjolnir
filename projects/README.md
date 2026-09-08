<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Projects

> [!WARNING]
> **DEPRECATION NOTICE: Centralized Direct Project Integration**
> Adding or maintaining project configurations directly within Mjolnir's `projects/` directory is **deprecated**.
>
> Mjolnir has transitioned to a **decentralized, repository-native architecture**. Adopting projects should maintain their own Mjolnir configuration directory (`./tools/mjolnir/` or `./mjolnir/`), threat models, jobs, and CI workflows natively within their own repositories (as implemented by `caliptra-sw`, `caliptra-mcu-sw`, and `caliptra-dpe`).
>
> Please refer to the [Mjolnir Integration Guide](../INTEGRATION_GUIDE.md) for instructions on integrating Mjolnir directly into your target repository.

This directory contains legacy centralized definitions for projects supported by Mjolnir.

## Existing Projects

- [OpenTitan](./opentitan/): OpenTitan's main repository (legacy built-in configuration).

## Adding a New Project (Deprecated Workflow)

> [!IMPORTANT]
> New projects should follow the decentralized model in the [Mjolnir Integration Guide](../INTEGRATION_GUIDE.md). The instructions below are retained only for legacy reference.

To add a legacy centralized project target to Mjolnir, you need to create a project folder under `projects/` with the following structure:

```
projects/
└── your-new-project/
    ├── project.nix
    ├── jobs/
    │   └── my-job.nix
    └── shell.nix              # Optional: Nix devShell for firmware/compiler toolchain
```

The Nix pipeline uses `discovery.nix` to automatically locate these folders, parse the attributes, and generate the corresponding `nix run .#<project-name>-<job-name>` targets.

---

### Project Configuration (`project.nix`)

The `project.nix` file defines the repository and global settings for the project. It is a Nix attribute set.

#### Schema

- **`name`** (String, Required): Human-readable name of the project.
- **`repoName`** (String, Required): Name of the repository folder when checked out.
- **`repoUrl`** (String, Required): HTTPS git URL of the target repository.
- **`commit`** (String, Optional): Default git commit hash or branch to checkout.
- **`threatModel`** (Path, Optional): Path to a threat model Markdown file (`threat_model.md`) containing context and security requirements.
- **`shell`** (Path, Optional): Path to a Nix development shell file (defaults to `./shell.nix` if present).

- **`outputDir`** (String, Required): Relative path where audit results are stored (e.g. `"./test-out/results"`).
- **`workspaceDir`** (String, Required): Relative path where temporary analysis workspaces are created (e.g. `"./test-out/workspace"`).

- **`defaultModel`** (String, Required unless set in job): Default AI foundation model (e.g. `"gemini-3.6-flash"`).
- **`defaultProvider`** (String, Required unless set in job): Default backend engine (`"adk"`, `"genai"`, or `"mock"`).
- **`defaultBatchSize`** (Integer, Required unless set in job): Default batch window size for agent analysis (e.g. `64`).
- **`defaultExtensions`** (List of Strings, Required unless set in job): Default source file extensions to audit (e.g. `["rs", "c", "h"]`).

#### Example

```nix
{
  name = "My Root of Trust Project";
  repoName = "my-rot-project";
  repoUrl = "https://github.com/example/my-rot-project.git";
  threatModel = ./threat_model.md;
  outputDir = "./test-out/results";
  workspaceDir = "./test-out/workspace";

  defaultModel = "gemini-3.6-flash";
  defaultProvider = "adk";
  defaultBatchSize = 64;
  defaultExtensions = [ "rs" "c" "h" ];
}
```

---

### Job Configuration (`jobs/*.nix`)

Each file under `jobs/` defines a specific audit task (e.g., scanning PR diffs, auditing a specific branch, using a distinct model).

#### Schema

- **`name`** (String, Required / inferred from filename): Human-readable name of the job.
- **`branch`** (String, Optional): Git branch to checkout (e.g., `main`).
- **`tag`** (String, Optional): Git tag to checkout (e.g., `v1.0`).
- **`commit`** (String, Optional): Git commit hash (SHA-1) to checkout.
- **`localDir`** (String, Optional): Explicit relative path to a local repository directory to audit directly (e.g., `"."`), bypassing remote git cloning and workspace isolation.
- **`diffBase`** (String, Optional): Git diff base revision (e.g., `main` or `HEAD~1`).
- **`diffHead`** (String, Optional): Git diff head revision (defaults to `"HEAD"`).
- **`srcDirs`** (List of Strings, Optional): Subdirectories within the repo to scan. Defaults to `[ "." ]` (scans everything).
- **`maxFiles`** (Integer, Optional): Cap the maximum number of files to scan.
- **`cmd`** (String, Optional): Build or verification command to run inside the development shell context.
- **`ingestionReport`** (String, Optional): Path to an existing vulnerability report (CSV/JSON/SARIF) to ingest.
- **`model`** (String, Optional): Override the model to use (defaults to `project.defaultModel`).
- **`provider`** (String, Optional): Override the analysis provider (defaults to `project.defaultProvider`).
- **`batchSize`** (Integer, Optional): Number of concurrent tasks / files to process per batch (defaults to `project.defaultBatchSize`).
- **`extensions`** (List of Strings, Optional): Override file extensions to scan (defaults to `project.defaultExtensions`).

#### Example

```nix
{
  name = "CI";
  srcDirs = [ "." ];
}
```

---

### Hermetic Compilation (`shell.nix`)

If your project requires compilation for tests, verification, or if the python toolchain needs to invoke build commands (`cmd`), provide a standard `shell.nix` (`pkgs.mkShell`).

Mjolnir will automatically inject the development shell's tools into `PATH` and execute any configured `shellHook` during job execution.
