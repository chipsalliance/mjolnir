<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Caliptra MCU SW Configurations

Audit targets and job specifications for the Caliptra MCU Software repository.

## Components

- **`project.nix`**: Core project definition mapping to `https://github.com/chipsalliance/caliptra-mcu-sw.git`.
- **`shell.nix`**: Nix development shell providing the RISC-V Rust cross-compiler toolchain.
- **`jobs/`**: Job configurations to target specific branches:
  - `main.nix`: Scans the `main` branch.
  - `ci.nix`: PR diff scanning job.
