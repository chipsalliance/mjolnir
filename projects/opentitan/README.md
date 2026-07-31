<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OpenTitan configurations

Audit targets and job specifications for the OpenTitan repository.

## Components

- **`project.nix`**: Core project definition mapping to `https://github.com/lowRISC/opentitan.git` and registering its threat model.
- **`jobs/`**: Job configurations targeting specific subsystems.
  - `crypto.nix`: Scans `sw/device/lib/crypto` code on the `earlgrey_1.0.0` branch.
  - `lib.nix`: Scans `sw/device/silicon_creator/lib` code on the `earlgrey_1.0.0` branch.
  - `manuf.nix`: Scans `sw/device/silicon_creator/manuf/` code on the `earlgrey_1.0.0` branch.
  - `rom.nix`: Scans `sw/device/silicon_creator/rom/` code on the `earlgrey_1.0.0` branch.
  - `rom_ext.nix`: Scans `sw/device/silicon_creator/rom_ext/` code on the `earlgrey_1.0.0` branch.
- **`nix/`**: Nix environment build setups.
  - `flake.nix`: Packages local compilation toolchains.
  - `runner.nix`: Helper script to build targets.
  - `runner-host-test.nix`: Wraps host test execution.
  - `runner-verilator-test.nix`: Wraps verilator test execution.
