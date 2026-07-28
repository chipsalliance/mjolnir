# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  description = "OpenTitan static environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    nixpkgs-v4.url = "github:NixOS/nixpkgs/nixos-22.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, nixpkgs-v4, flake-utils }:
    flake-utils.lib.eachSystem [ "x86_64-linux" "aarch64-linux" ] (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pkgs-v4 = nixpkgs-v4.legacyPackages.${system};
        
        runner = import ./runner.nix {
          inherit pkgs pkgs-v4;
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
        makeRunner = { pkgs, pkgs-v4 }: import ./runner.nix {
          inherit pkgs pkgs-v4;
        };
      };
    };
}
