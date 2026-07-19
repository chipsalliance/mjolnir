''
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
''
