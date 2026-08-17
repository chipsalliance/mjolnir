# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  description = "Mjolnir: AI Security Analysis Tool";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    nixpkgs-v4.url = "github:NixOS/nixpkgs/nixos-22.05";
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, nixpkgs-v4, rust-overlay }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      overlays = [ (import rust-overlay) ];
      nixpkgsFor = forAllSystems (system: import nixpkgs { inherit system overlays; });

      autodiscoverJobs = import ./nix/discovery.nix;
    in
    {
      lib = {
        discoverProjectJobs = import ./nix/discover_project.nix;
        makeJob = import ./nix/orchestrator.nix;
        makeGroup = import ./nix/group.nix;
      };


      packages = forAllSystems (system:
        let
          pkgs = nixpkgsFor.${system};
          pkgs-v4 = nixpkgs-v4.legacyPackages.${system};




          google-genai-latest = pkgs.python3Packages.google-genai.overridePythonAttrs (old: rec {
            version = "2.10.0";
            src = pkgs.python3Packages.fetchPypi {
              pname = "google_genai";
              inherit version;
              hash = "sha256-d5Es1VjNff1bdcJf0cYJ5415VN3lgzMRBAIqRuqQ+e4=";
            };
            dontCheckRuntimeDeps = true;
            catchConflicts = false;
            nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [ pkgs.python3Packages.pythonRelaxDepsHook ];
            pythonRelaxDeps = [ "google-auth" ];
            doCheck = false;
          });



          google-adk = pkgs.python3Packages.buildPythonPackage {
            pname = "google-adk";
            version = "2.4.0";
            pyproject = true;
            src = pkgs.python3Packages.fetchPypi {
              pname = "google_adk";
              version = "2.4.0";
              hash = "sha256-WimWsojVkd7vyyd+7ut9qDjXIFZnV2O/71KtOzaXXd4=";
            };
            postPatch = import ./nix/adk_telemetry_patch.nix;
            nativeBuildInputs = with pkgs.python3Packages; [
              flit-core
            ];
            dontCheckRuntimeDeps = true;
            dependencies = with pkgs.python3Packages; [
              google-genai-latest
              pydantic
              aiosqlite
              authlib
              fastapi
              click
              jsonschema
              pyyaml
              python-dotenv
              python-multipart
              uvicorn
              websockets
              watchdog
              tzlocal
              opentelemetry-api
              opentelemetry-sdk
              packaging
            ];
            pythonImportsCheck = [ "google.adk" ];
            doCheck = false;
          };

          pythonEnv = pkgs.python3.withPackages (ps: [
            ps.pydantic
            google-genai-latest
            ps.google-cloud-storage
            ps.pyopenssl
            ps.tqdm
            ps.pandas
            ps.openpyxl
            ps.tabulate
            google-adk
          ]);

          mjolnir-app = pkgs.stdenv.mkDerivation {
            name = "mjolnir-app";
            src = ./app/mjolnir;
            
            nativeBuildInputs = [ pkgs.makeWrapper ];
            
            installPhase = ''
              mkdir -p $out/bin $out/lib
              cp -r * $out/lib/
              
              makeWrapper ${pythonEnv}/bin/python3 $out/bin/mjolnir-run \
                --add-flags "$out/lib/main.py" \
                --prefix PYTHONPATH : "$out/lib" \
                --prefix PATH : "${pkgs.lib.makeBinPath [ pkgs.git pkgs.ripgrep pkgs.universal-ctags pkgs.ast-grep ]}" \
                --set GOOGLE_API_USE_CLIENT_CERTIFICATE false
            '';
          };

          makeJob = { project, job, devShell ? null }: 
            import ./nix/orchestrator.nix {
              inherit pkgs project job devShell mjolnir-app;
            };

          makeGroup = { name, description, jobs }:
            import ./nix/group.nix { inherit pkgs; } {
              inherit name description jobs;
            };

          discovered = autodiscoverJobs { inherit pkgs makeJob; };

          web-viewer = pkgs.writeShellApplication {
            name = "mjolnir-web-viewer";
            runtimeInputs = [ pkgs.cargo pkgs.rustc pkgs.wasm-bindgen-cli pkgs.lld ];
            text = ''
              cargo xtask web --serve "$@"
            '';
          };

          deploy-gcs-web = pkgs.writeShellApplication {
            name = "mjolnir-deploy-gcs-web";
            runtimeInputs = [ pkgs.cargo pkgs.rustc pkgs.wasm-bindgen-cli pkgs.lld pythonEnv ];
            text = ''
              export PYTHONPATH="${./app}:''${PYTHONPATH:-}"
              exec cargo xtask deploy-gcs-web "$@"
            '';
          };

          deploy-gcs-runs = pkgs.writeShellApplication {
            name = "mjolnir-deploy-gcs-runs";
            runtimeInputs = [ pythonEnv ];
            text = ''
              export PYTHONPATH="${./app}:''${PYTHONPATH:-}"
              exec python3 "${./scripts/deploy_gcs_runs.py}" "$@"
            '';
          };


        in
          discovered // {
            inherit
              mjolnir-app
              web-viewer
              deploy-gcs-web
              deploy-gcs-runs;

            test-all = makeGroup {
              name = "test-all";
              description = "All tests";
              jobs = [
                discovered.mock-smoke-test
                discovered.mock-ci-test
                discovered.genai-ci-test
                discovered.genai-gemini-test
                discovered.adk-ci-test
                discovered.adk-gemini-test
                discovered.adk-gemini-ingest-test
              ];
            };

            caliptra-all = makeGroup {
              name = "caliptra-all";
              description = "All Caliptra jobs";
              jobs = [
                discovered.caliptra-sw-main
                discovered.caliptra-sw-rom-main
                discovered.caliptra-sw-caliptra-1x
                discovered.caliptra-mcu-sw-main
              ];
            };

            opentitan-all = makeGroup {
              name = "opentitan-all";
              description = "All OpenTitan jobs";
              jobs = [
                discovered.opentitan-crypto
                discovered.opentitan-lib
                discovered.opentitan-manuf
                discovered.opentitan-rom
                discovered.opentitan-rom_ext
              ];
            };
          }
      );
    };
}

