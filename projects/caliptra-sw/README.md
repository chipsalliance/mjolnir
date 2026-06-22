# Caliptra SW configurations

Audit targets and job specifications for the Caliptra Firmware/Software repository.

## Components

- **`project.nix`**: Core project definition mapping to `https://github.com/chipsalliance/caliptra-sw.git` and registering its threat model.
- **`jobs/`**: Job configurations to target specific subdirectories.
  - `rom-main.nix`: Scans `rom/dev/src` code on the `main` branch.
- **`nix/`**: Nix environment build setups.
  - `flake.nix`: Packages local RISC-V compilation toolchains.
  - `runner.nix`: Helper script to compile firmware and run tests/emulator.
  - `runner-test.nix`: Wraps the compile-testing logic.
