<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Caliptra SW Configurations

Audit targets and job specifications for the Caliptra Firmware/Software repository.

## Components

- **`project.nix`**: Core project definition mapping to `https://github.com/chipsalliance/caliptra-sw.git` and registering its threat model.
- **`shell.nix`**: Nix development shell providing the RISC-V Rust cross-compiler and build tools.
- **`jobs/`**: Job configurations targeting specific branches and directories:
  - `main.nix`: Scans the `main` branch.
  - `ci.nix`: PR diff scanning job.
  - `rom-main.nix`: Scans `rom/dev/src` code on the `main` branch.
  - `caliptra-1x.nix`: Scans the Caliptra 1.x release branch.
