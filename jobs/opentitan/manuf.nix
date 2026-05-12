# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs }:
import ./base.nix { inherit pkgs; } {
  subjobName = "MANUF";
  subdir = "manuf";
  searchPath = "sw/device/silicon_creator/manuf";
}
