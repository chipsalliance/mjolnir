{
  description = "Caliptra SW static environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, rust-overlay }:
    flake-utils.lib.eachSystem [ "x86_64-linux" "aarch64-linux" ] (system:
      let
        overlays = [ (import rust-overlay) ];
        pkgs = import nixpkgs {
          inherit system overlays;
        };

        rustToolchain = pkgs.rust-bin.stable."1.85.0".default.override {
          extensions = [ "rust-src" "llvm-tools-preview" ];
          targets = [ "riscv32imc-unknown-none-elf" ];
        };

        runner = import ./runner.nix {
          inherit pkgs rustToolchain;
        };
      in {
        packages = {
          default = runner;
        };

        apps = {
          default = flake-utils.lib.mkApp { drv = runner; };
        };
      }
    ) // {
      lib = {
        makeRunner = { pkgs, rustToolchain }: import ./runner.nix {
          inherit pkgs rustToolchain;
        };
      };
    };
}
