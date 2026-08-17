# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{ pkgs ? import <nixpkgs> {} }:
let
  rustToolchain = pkgs.rust-bin.stable."1.85.0".default.override {
    extensions = [ "rust-src" "llvm-tools-preview" ];
    targets = [ "riscv32imc-unknown-none-elf" ];
  };
in
pkgs.mkShell {
  name = "caliptra-mcu-sw-shell";
  nativeBuildInputs = [
    rustToolchain
    pkgs.git
    pkgs.pkg-config
    pkgs.openssl
    pkgs.gcc
  ];
}
