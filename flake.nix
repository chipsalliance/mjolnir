# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  description = "AI Security Analysis Orchestration Tool";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      nixpkgsFor = forAllSystems (system: import nixpkgs { inherit system; });
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = nixpkgsFor.${system};

          # Function to create the orchestrator package based on a job file
          makeOrchestrator = { jobFile }: import ./orchestrator.nix {
            inherit pkgs jobFile;
            orchestratorCommit = self.rev or "dirty";
          };
          # Function to create a group of jobs to run sequentially
          makeJobGroup = import ./job_group.nix { inherit pkgs; };

          # Individual (test) jobs
          smoke-test = makeOrchestrator { jobFile = ./jobs/smoke-test.nix; };
          postprocessing-test = makeOrchestrator { jobFile = ./jobs/tests/postprocessing-test.nix; };

          # Individual (real) jobs
          caliptra-sw-2p1-latest = makeOrchestrator { jobFile = ./jobs/caliptra-sw-2p1-latest.nix; };
          caliptra-mcu-sw-2p0-latest = makeOrchestrator { jobFile = ./jobs/caliptra-mcu-sw-2p0-latest.nix; };
          caliptra-dpe-latest = makeOrchestrator { jobFile = ./jobs/caliptra-dpe-latest.nix; };
          caliptra-dpe-1x = makeOrchestrator { jobFile = ./jobs/caliptra-dpe-1x.nix; };
          opentitan-rom = makeOrchestrator { jobFile = ./jobs/opentitan/rom.nix; };
          opentitan-rom-ext = makeOrchestrator { jobFile = ./jobs/opentitan/rom_ext.nix; };
          opentitan-manuf = makeOrchestrator { jobFile = ./jobs/opentitan/manuf.nix; };
          opentitan-lib = makeOrchestrator { jobFile = ./jobs/opentitan/lib.nix; };
          opentitan-crypto = makeOrchestrator { jobFile = ./jobs/opentitan/crypto.nix; };

          # Group (test) jobs
          scan-all-test = makeJobGroup {
            name = "scan-all-test";
            description = "All Test/Smoke Vulnerability Scans";
            jobs = [
              { name = "smoke-test"; pkg = smoke-test; }
            ];
          };

          # Group (real) jobs
          scan-all = makeJobGroup {
            name = "scan-all";
            description = "All Vulnerability Scans";
            jobs = [
              { name = "caliptra-sw-2p1-latest"; pkg = caliptra-sw-2p1-latest; }
              { name = "caliptra-mcu-sw-2p0-latest"; pkg = caliptra-mcu-sw-2p0-latest; }
              { name = "caliptra-dpe-1x"; pkg = caliptra-dpe-1x; }
              { name = "opentitan-rom"; pkg = opentitan-rom; }
              { name = "opentitan-rom-ext"; pkg = opentitan-rom-ext; }
              { name = "opentitan-manuf"; pkg = opentitan-manuf; }
              { name = "opentitan-lib"; pkg = opentitan-lib; }
              { name = "opentitan-crypto"; pkg = opentitan-crypto; }
            ];
          };

          opentitan-all = makeJobGroup {
            name = "opentitan-all";
            description = "All OpenTitan Vulnerability Scans";
            jobs = [
              { name = "opentitan-rom"; pkg = opentitan-rom; }
              { name = "opentitan-rom-ext"; pkg = opentitan-rom-ext; }
              { name = "opentitan-manuf"; pkg = opentitan-manuf; }
              { name = "opentitan-lib"; pkg = opentitan-lib; }
              { name = "opentitan-crypto"; pkg = opentitan-crypto; }
            ];
          };
        in
        {
          inherit smoke-test postprocessing-test
                  caliptra-sw-2p1-latest caliptra-mcu-sw-2p0-latest
                  opentitan-rom opentitan-rom-ext opentitan-manuf opentitan-lib opentitan-crypto
                  opentitan-all
                  caliptra-dpe-latest
                  caliptra-dpe-1x
                  scan-all scan-all-test;
        }
      );
    };
}
