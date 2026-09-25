<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OpenPRoT Configurations

Audit targets and job specifications for the OpenPRoT (Open Platform Root of Trust) repository.

## Components

- **`project.nix`**: Core project definition mapping to `https://github.com/OpenPRoT/openprot.git` and registering its threat model.
- **`threat_model.md`**: Platform RoT threat model detailing trust boundaries, attack surfaces, and critical security invariants across Hubris/Tock IPC, MCTP/PLDM/SPDM stacks, and hardware drivers.
- **`shell.nix`**: Nix development shell providing the Rust nightly cross-compiler (`thumbv6m-none-eabi`, `thumbv7em-none-eabihf`, `thumbv8m.main-none-eabihf`, `riscv32imac-unknown-none-elf`), `cargo-nextest`, `qemu`, and `verilator`.
- **`jobs/`**: Job configurations to target specific branches:
  - `main.nix`: Scans the `main` branch.
