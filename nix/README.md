<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Nix Infrastructure

This directory contains the Nix expressions that define the build and execution environment for Mjolnir, as well as job orchestration.

## Files

- `orchestrator.nix`: Defines the function to package a single job. It:
  - Accepts project and job definitions.
  - Serializes the job configuration into a JSON spec file in the Nix store.
  - Sets default values for the job, including the `provider` (defaulting to `"genai"` globally, or `"mock"` if the project is `"tests"`).
  - Creates a wrapper script (`mjolnir-orchestrator-...`) that runs `mjolnir-run` with the generated spec.
- `discovery.nix`: Automatically scans the `projects/` directory to discover all projects and their jobs, converting them into Nix packages.
- `group.nix`: A helper to group multiple jobs together (e.g., `test-all` or `caliptra-all`) so they can be run sequentially.

## How it works

The root `flake.nix` imports these expressions to dynamically generate the packages available for `nix run`.

When you run `nix run .#<job-name>`, Nix:

1.  Evaluates the job definition (from `projects/<project>/jobs/<job>.nix`).
2.  Generates the job spec JSON.
3.  Creates a launcher script that wraps `mjolnir-app` and passes the spec.
4.  Executes the launcher script in an environment with required tools (like `git` and `ripgrep`).
