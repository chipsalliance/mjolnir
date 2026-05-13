# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ./base.nix { inherit pkgs; } {
  subjobName = "ROM_EXT";
  subdir = "rom_ext";
  searchPath = [
    "sw/device/silicon_creator/rom_ext"
  ];
}
