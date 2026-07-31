<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Caliptra DPE configurations

Audit targets and job specifications for the Caliptra DPE (Dice Protection Environment) repository.

## Components

- **`project.nix`**: Core project definition mapping to `https://github.com/chipsalliance/caliptra-dpe.git`.
- **`jobs/`**: Job configurations to target specific branches.
  - `main.nix`: Scans the `main` branch.
  - `runtime-v1.nix`: Scans the `runtime-v1` branch.
- **`nix/`**: Nix environment build setups.
  - `flake.nix`: Packages local compilation toolchains.
  - `runner.nix`: Helper script to build/test the workspace code locally.
  - `runner-test.nix`: Wraps the compile-testing logic.
