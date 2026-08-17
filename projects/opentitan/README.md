<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OpenTitan Configurations

Audit targets and job specifications for the OpenTitan repository.

## Components

- **`project.nix`**: Core project definition mapping to `https://github.com/lowRISC/opentitan.git` and registering its threat model.
- **`shell.nix`**: Nix development shell providing Bazel, Verilator, Clang, and build libraries.
- **`jobs/`**: Job configurations targeting specific subsystems:
  - `ci.nix`: PR diff scanning job.
  - `crypto.nix`: Scans `sw/device/lib/crypto` code on the `earlgrey_1.0.0` branch.
  - `lib.nix`: Scans `sw/device/silicon_creator/lib` code on the `earlgrey_1.0.0` branch.
  - `manuf.nix`: Scans `sw/device/silicon_creator/manuf/` code on the `earlgrey_1.0.0` branch.
  - `rom.nix`: Scans `sw/device/silicon_creator/rom/` code on the `earlgrey_1.0.0` branch.
  - `rom_ext.nix`: Scans `sw/device/silicon_creator/rom_ext/` code on the `earlgrey_1.0.0` branch.
