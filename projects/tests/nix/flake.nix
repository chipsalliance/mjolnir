{
  description = "Mjolnir Test environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachSystem [ "x86_64-linux" "aarch64-linux" ] (system:
      let
        pkgs = import nixpkgs { inherit system; };
        runner = pkgs.writeShellScriptBin "test-runner" "echo 'Test environment runner: OK'";
      in {
        packages = {
          default = runner;
        };
        apps = {
          default = flake-utils.lib.mkApp { drv = runner; };
        };
      }
    );
}
