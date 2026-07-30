# Projects

This directory contains definitions for each project currently supported by Mjolnir.

## Existing Projects

- [Caliptra DPE](./caliptra-dpe/): Caliptra's DPE repository.
- [Caliptra MCU SW](./caliptra-mcu-sw/): Caliptra's MCU SW repository.
- [Caliptra SW](./caliptra-sw/): Caliptra's SW repository.
- [OpenTitan](./opentitan/): OpenTitan's main repository.

## Adding a New Project

To add a new project target to Mjolnir, you need to create a project folder under `projects/` with the following structure:

```
projects/
└── your-new-project/
    ├── project.nix
    ├── jobs/
    │   └── my-job.nix
    └── nix/                   # Optional: For compiling firmware/verification tools
        ├── flake.nix
        ├── runner.nix
        └── runner-test.nix
```

The Nix pipeline uses `discovery.nix` to automatically locate these folders, parse the attributes, and generate the corresponding `nix run .#<project-name>-<job-name>` targets.

---

### Project Configuration (`project.nix`)

The `project.nix` file defines the repository and global settings for the project. It is a Nix attribute set.

#### Schema

- **`name`** (String, Required): Human-readable name of the project.
- **`repoName`** (String, Required): Name of the repository folder when checked out.
- **`repoUrl`** (String, Required): HTTPS git URL of the target repository.
- **`srcExtensions`** (List of Strings, Required): File extensions relevant to this project (e.g., `["rs", "c", "h"]`).
- **`threatModel`** (Path, Optional): Path to a pre-generated threat model Markdown file (`THREAT_MODEL.md`) containing context and security requirements.
- **`model`** (String, Optional): Default Gemini model to use for this project (defaults to `gemini-3.6-flash`).
- **`provider`** (String, Optional): Default provider (e.g. `genai` or `mock`).
- **`requireGcsUpload`** (Boolean, Optional): Set to `true` to require uploading scan results to GCS (defaults to `false`).

#### Example

```nix
{
  name = "Caliptra SW";
  repoName = "caliptra-sw";
  repoUrl = "https://github.com/chipsalliance/caliptra-sw.git";
  requireGcsUpload = true;
  srcExtensions = [ "rs" "c" "h" "sv" ];
  threatModel = ../../app/mjolnir/providers/genai/threat-models/caliptra/THREAT_MODEL.md;
}
```

---

### Job Configuration (`jobs/*.nix`)

Each file under `jobs/` defines a specific audit task (e.g., scanning ROM firmware, checking a subdirectory, using a specific model).

#### Schema

- **`name`** (String, Required): Human-readable name of the job.
- **`model`** (String, Optional): Override the model to use (e.g., `gemini-1.5-pro` for deeper analysis, defaults to project default).
- **`provider`** (String, Optional): Override the analysis provider (`genai` or `mock`).
- **`batchSize`** (Integer, Optional): Number of files to process per batch (defaults to `20`).
- **`branch`** (String, Optional): Git branch to checkout (e.g., `main`).
- **`tag`** (String, Optional): Git tag to checkout (e.g., `v1.0`).
- **`commit`** (String, Optional): Git commit hash (SHA-1) to checkout.
- **`srcDirs`** (List of Strings, Optional): Subdirectories within the repo to scan. Defaults to `[ "." ]` (scans everything).
- **`extensions`** (List of Strings, Optional): Override file extensions to scan for this job.
- **`maxFiles`** (Integer, Optional): Cap the maximum number of files to scan.
- **`requireGcsUpload`** (Boolean, Optional): Override GCS upload requirements.
- **`cmd`** (String, Optional): Build or verification command to run inside the compilation runner context.

#### Example

```nix
{
  name = "ROM Main";
  branch = "main";
  srcDirs = [ "rom/dev/src" ];
}
```

---

### Hermetic Compilation (Optional, `nix/`)

If your project requires compilation for tests, verification, or if the python tool chain needs to invoke build commands, you should provide a local `nix/` structure.

- `nix/flake.nix` exports a `default` package that exposes the compiler toolchain wrapper script (`runner.nix`).
- The global Mjolnir orchestrator will automatically prepend this package's `/bin` to the `PATH` during job execution if a runner is supplied.
