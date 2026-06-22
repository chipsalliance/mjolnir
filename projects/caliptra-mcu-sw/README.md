# Caliptra MCU SW configurations

Audit targets and job specifications for the Caliptra MCU Software repository.

## Components

- **`project.nix`**: Core project definition mapping to `https://github.com/chipsalliance/caliptra-mcu-sw.git`.
- **`jobs/`**: Job configurations to target specific branches.
  - `main.nix`: Scans the `main` branch.
- **`nix/`**: Nix environment build setups.
  - `flake.nix`: Packages local compilation toolchains.
  - `runner.nix`: Helper script to build/test the workspace code locally.
  - `runner-test.nix`: Wraps the compile-testing logic.
