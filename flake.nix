# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
{
  description = "Mjolnir: AI Security Analysis Tool";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";

    # Local Project Flakes (providing hermetic compiler environments)
    opentitan-env.url = "path:./projects/opentitan/nix";
    caliptra-sw-env.url = "path:./projects/caliptra-sw/nix";
    caliptra-mcu-sw-env.url = "path:./projects/caliptra-mcu-sw/nix";
    caliptra-dpe-env.url = "path:./projects/caliptra-dpe/nix";
    tests-env.url = "path:./projects/tests/nix";
  };

  outputs = { self, nixpkgs, opentitan-env, caliptra-sw-env, caliptra-mcu-sw-env, caliptra-dpe-env, tests-env }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      nixpkgsFor = forAllSystems (system: import nixpkgs { inherit system; });

      autodiscoverJobs = import ./nix/discovery.nix;
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = nixpkgsFor.${system};

          runners = {
            caliptra-sw = caliptra-sw-env.packages.${system}.default;
            opentitan = opentitan-env.packages.${system}.default;
            caliptra-mcu-sw = caliptra-mcu-sw-env.packages.${system}.default;
            caliptra-dpe = caliptra-dpe-env.packages.${system}.default;
            tests = tests-env.packages.${system}.default;
          };

          google-genai-latest = pkgs.python3Packages.google-genai.overridePythonAttrs (old: rec {
            version = "2.10.0";
            src = pkgs.python3Packages.fetchPypi {
              pname = "google_genai";
              inherit version;
              hash = "sha256-d5Es1VjNff1bdcJf0cYJ5415VN3lgzMRBAIqRuqQ+e4=";
            };
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
            postPatch = ''
              # Replace incubating OTel imports in ADK telemetry files with safe fallback definitions
              for f in src/google/adk/telemetry/_experimental_semconv.py \
                       src/google/adk/telemetry/tracing.py \
                       src/google/adk/telemetry/_metrics.py \
                       src/google/adk/telemetry/_token_usage.py; do
                if [ -f "$f" ]; then
                  sed -i -E 's/from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import.*/# otel semconv patch/g' "$f"
                  sed -i -E 's/from opentelemetry.semconv._incubating.attributes import gen_ai_attributes/# otel semconv module patch/g' "$f"
                fi
              done
              
              cat << 'EOF' > src/google/adk/telemetry/_otel_compat.py
class DummyAttr(str):
    value = "gemini"
    name = "gemini"
    def lower(self):
        return "gemini"

GEN_AI_INPUT_MESSAGES = "gen_ai.input.messages"
GEN_AI_OUTPUT_MESSAGES = "gen_ai.output.messages"
GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
GEN_AI_SYSTEM_INSTRUCTIONS = "gen_ai.system_instructions"
GEN_AI_TOOL_DEFINITIONS = "gen_ai.tool_definitions"
GEN_AI_AGENT_DESCRIPTION = "gen_ai.agent.description"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_TOOL_CALL_ID = "gen_ai.tool.call_id"
GEN_AI_TOOL_DESCRIPTION = "gen_ai.tool.description"
GEN_AI_TOOL_NAME = "gen_ai.tool.name"
GEN_AI_TOOL_TYPE = "gen_ai.tool.type"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_TOKEN_TYPE = "gen_ai.token.type"
class GenAiSystemValues:
    GEMINI = DummyAttr("gemini")
    VERTEX_AI = DummyAttr("vertex_ai")
EOF

              for f in src/google/adk/telemetry/_experimental_semconv.py \
                       src/google/adk/telemetry/tracing.py \
                       src/google/adk/telemetry/_metrics.py \
                       src/google/adk/telemetry/_token_usage.py; do
                if [ -f "$f" ]; then
                  substituteInPlace "$f" \
                    --replace-warn "# otel semconv patch" "from ._otel_compat import *" \
                    --replace-warn "# otel semconv module patch" "from . import _otel_compat as gen_ai_attributes"
                fi
              done
              substituteInPlace src/google/adk/telemetry/tracing.py \
                --replace-fail "Schemas.V1_36_0.value" "'https://opentelemetry.io/schemas/1.36.0'" \
                --replace-fail "event_name=" "# event_name="
              substituteInPlace src/google/adk/flows/llm_flows/basic.py \
                --replace-fail "llm_request.live_connect_config.avatar_config" "_avatar_config"
              substituteInPlace src/google/adk/agents/run_config.py \
                --replace-fail "types.AvatarConfig" "Any"
              substituteInPlace src/google/adk/models/google_llm.py \
                --replace-fail "return Client(**kwargs)" \
                               "import os; vertexai = os.environ.get(\"GOOGLE_GENAI_USE_VERTEXAI\", \"\").lower() in (\"true\", \"1\") or bool(os.environ.get(\"GOOGLE_CLOUD_PROJECT\")); return Client(vertexai=vertexai, **kwargs) if vertexai else Client(**kwargs)"
            '';
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

          makeJob = { project, job, runner ? null }: 
            import ./nix/orchestrator.nix {
              inherit pkgs project job runner mjolnir-app;
            };

          makeGroup = { name, description, jobs }:
            import ./nix/group.nix { inherit pkgs; } {
              inherit name description jobs;
            };

          discovered = autodiscoverJobs { inherit pkgs makeJob runners; };

          caliptra-sw-runner-test = makeJob {
            project = import ./projects/caliptra-sw/project.nix;
            job = import ./projects/caliptra-sw/nix/runner-test.nix;
            runner = runners.caliptra-sw;
          };

          caliptra-mcu-sw-runner-test = makeJob {
            project = import ./projects/caliptra-mcu-sw/project.nix;
            job = import ./projects/caliptra-mcu-sw/nix/runner-test.nix;
            runner = runners.caliptra-mcu-sw;
          };

          caliptra-dpe-runner-test = makeJob {
            project = import ./projects/caliptra-dpe/project.nix;
            job = import ./projects/caliptra-dpe/nix/runner-test.nix;
            runner = runners.caliptra-dpe;
          };

          opentitan-runner-host-test = makeJob {
            project = import ./projects/opentitan/project.nix;
            job = import ./projects/opentitan/nix/runner-host-test.nix;
            runner = runners.opentitan;
          };

          opentitan-runner-verilator-test = makeJob {
            project = import ./projects/opentitan/project.nix;
            job = import ./projects/opentitan/nix/runner-verilator-test.nix;
            runner = runners.opentitan;
          };

          gen-dashboard = pkgs.writeShellApplication {
            name = "mjolnir-gen-dashboard";
            runtimeInputs = [ mjolnir-app ];
            text = ''
              mjolnir-run --gen-dashboard "$@"
            '';
          };
        in
          discovered // {
            inherit
              mjolnir-app
              gen-dashboard
              caliptra-sw-runner-test
              caliptra-mcu-sw-runner-test
              caliptra-dpe-runner-test
              opentitan-runner-host-test
              opentitan-runner-verilator-test;

            test-all = makeGroup {
              name = "test-all";
              description = "All tests";
              jobs = [
                discovered.mock-smoke-test
                discovered.mock-gcs-test
                discovered.genai-gemini-test
                discovered.genai-gemini-gcs-test
                discovered.adk-gemini-test
                discovered.adk-gemini-gcs-test
                discovered.adk-gemini-ingest-test
              ];
            };

            test-all-runners = makeGroup {
              name = "test-all-runners";
              description = "All runner tests";
              jobs = [
                caliptra-sw-runner-test
                caliptra-mcu-sw-runner-test
                caliptra-dpe-runner-test
                opentitan-runner-host-test
                opentitan-runner-verilator-test
              ];
            };

            caliptra-all = makeGroup {
              name = "caliptra-all";
              description = "All Caliptra jobs";
              jobs = [
                discovered.caliptra-sw-rom-main
                discovered.caliptra-mcu-sw-main
                discovered.caliptra-dpe-main
                discovered.caliptra-dpe-runtime-v1
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
