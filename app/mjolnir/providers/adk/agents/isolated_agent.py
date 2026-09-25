# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import json
import re
from typing import Any, Optional
from google.adk import Agent
from google.adk.agents.invocation_context import (
    InvocationContext,
    _InvocationCostManager,
)
from google.adk.agents.run_config import RunConfig
from google.adk.models import BaseLlm, LLMRegistry, LlmRequest
from google.adk.models.google_llm import Gemini
from google.adk.tools.set_model_response_tool import SetModelResponseTool
from google.genai import types

from constants import (
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_INITIAL_DELAY,
    DEFAULT_RETRY_MAX_DELAY,
)
from providers.adk.utilities.cache_manager import PhaseContextCache
from utilities.logger import logger

# Default transport-level retry configuration for LLM calls (exponential backoff with jitter)
DEFAULT_HTTP_RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=DEFAULT_RETRY_ATTEMPTS,
    initial_delay=DEFAULT_RETRY_INITIAL_DELAY,
    max_delay=DEFAULT_RETRY_MAX_DELAY,
)


class CachedGemini(Gemini):
    """ADK Gemini model wrapper that correctly handles Vertex AI explicit cached content and enables thinking trace visibility."""

    async def _preprocess_request(self, llm_request: LlmRequest) -> None:
        await super()._preprocess_request(llm_request)
        if llm_request.config:
            if cc := getattr(llm_request.config, "cached_content", None):
                llm_request.config.cached_content = PhaseContextCache._replacements.get(cc, cc)
            resp_schema = getattr(llm_request.config, "response_schema", None)
            if resp_schema and "set_model_response" not in llm_request.tools_dict:
                llm_request.tools_dict["set_model_response"] = SetModelResponseTool(resp_schema)
            if getattr(llm_request.config, "thinking_config", None) is None:
                llm_request.config.thinking_config = types.ThinkingConfig(include_thoughts=True)
            if getattr(llm_request.config, "cached_content", None):
                llm_request.config.system_instruction = None
                llm_request.config.tools = None
                llm_request.config.tool_config = None
            elif getattr(llm_request.config, "tools", None):
                # Ensure function declarations (such as set_model_response) are never duplicated by name
                for tool_entry in llm_request.config.tools:
                    if fns := getattr(tool_entry, "function_declarations", None):
                        tool_entry.function_declarations = list(
                            {getattr(f, "name", id(f)): f for f in fns}.values()
                        )

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False):
        cfg = llm_request.config
        orig_si = getattr(cfg, "system_instruction", None)
        orig_tools = getattr(cfg, "tools", None)
        orig_tool_cfg = getattr(cfg, "tool_config", None)
        try:
            async for resp in super().generate_content_async(llm_request, stream=stream):
                yield resp
        except Exception as e:
            cache_id = getattr(cfg, "cached_content", None)
            if not cache_id or "is expired" not in str(e).lower():
                raise
            cache = PhaseContextCache._instances.get(cache_id)
            new_cache_id = cache.create() if cache else None
            PhaseContextCache._replacements[cache_id] = new_cache_id
            logger.warning(
                f"Context cache {cache_id} expired; "
                + (
                    f"re-initialized as {new_cache_id}"
                    if new_cache_id
                    else "falling back to uncached inference"
                )
            )
            cfg.cached_content = new_cache_id
            cfg.system_instruction = orig_si
            cfg.tools = orig_tools
            cfg.tool_config = orig_tool_cfg
            async for resp in super().generate_content_async(llm_request, stream=stream):
                yield resp


def resolve_model_with_retries(model: str | BaseLlm) -> BaseLlm:
    """Polymorphically ensures any model (string name or instantiated BaseLlm) has transport-level retry options configured."""
    # 1. If passed an already-instantiated BaseLlm
    if isinstance(model, BaseLlm):
        if hasattr(model, "retry_options") and getattr(model, "retry_options", None) is None:
            model.retry_options = DEFAULT_HTTP_RETRY_OPTIONS
        return model

    # 2. If passed a string model name, resolve class dynamically via ADK registry
    llm_class = LLMRegistry.resolve(model)
    if issubclass(llm_class, Gemini):
        return CachedGemini(model=model, retry_options=DEFAULT_HTTP_RETRY_OPTIONS)

    # 3. Duck-type check if this provider class accepts `retry_options`
    if "retry_options" in getattr(llm_class, "model_fields", {}):
        return llm_class(model=model, retry_options=DEFAULT_HTTP_RETRY_OPTIONS)

    # 4. Fallback for non-retry-options providers
    return llm_class(model=model)


class IsolatedAgent(Agent):
    """An ADK Agent that isolates its LLM call counter and cost manager from the parent workflow session."""

    run_config: Optional[RunConfig] = None

    def __init__(self, **kwargs):
        if "model" in kwargs:
            kwargs["model"] = resolve_model_with_retries(kwargs["model"])
        super().__init__(**kwargs)

    def _create_invocation_context(self, parent_context: InvocationContext) -> InvocationContext:
        ctx = super()._create_invocation_context(parent_context)
        ctx._invocation_cost_manager = _InvocationCostManager()
        if self.run_config:
            ctx.run_config = self.run_config
        return ctx

    async def canonical_instruction(self, ctx: Any) -> tuple[str, bool]:
        """Bypasses ADK session state template substitution on instruction string.

        ADK attempts regex {var} variable substitution on agent instruction strings by default,
        which raises KeyError when code snippets containing curly braces appear in instructions.
        Returning bypass_state_injection=True disables this behavior.
        """
        raw_si, _ = await super().canonical_instruction(ctx)
        return raw_si, True

    def _is_final_model_text_event(self, event: Any) -> bool:
        """Returns True if event is a completed final model response requiring schema validation."""
        return bool(
            self.output_schema
            and not (hasattr(event, "get_function_calls") and event.get_function_calls())
            and not getattr(event, "partial", False)
            and getattr(event, "content", None)
            and getattr(event.content, "role", None) == "model"
            and getattr(event.content, "parts", None)
        )

    @staticmethod
    def _extract_json_candidates(raw_text: str) -> list[str]:
        """Extracts JSON object candidates from markdown code fences (last-to-first) or surrounding text."""
        candidates: list[str] = []
        # Match JSON objects wrapped in markdown code fences, e.g.:
        # ```json
        # {"vulnerabilities": [...]}
        # ```
        fenced_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, flags=re.DOTALL)
        for block in reversed(fenced_blocks):
            if stripped := block.strip():
                candidates.append(stripped)

        # Fallback for unfenced JSON surrounded by prose (e.g. "Here is the report: {...} Done."):
        # slice from the first '{' through the last '}' (inclusive via `end + 1` to keep `{...}`).
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end > start:
            outer = raw_text[start : end + 1].strip()
            if outer not in candidates:
                candidates.append(outer)
        return candidates

    def _coerce_to_schema_json(self, raw_text: str) -> Optional[str]:
        """Validates raw_text or an extracted JSON candidate against self.output_schema."""
        try:
            self.output_schema.model_validate_json(raw_text)
            return raw_text
        except Exception:
            pass

        for candidate in self._extract_json_candidates(raw_text):
            try:
                data = json.loads(candidate)
                if (
                    isinstance(data, dict)
                    and "vulnerabilities" not in data
                    and isinstance(data.get("findings"), list)
                ):
                    data["vulnerabilities"] = data.pop("findings")
                validated = self.output_schema.model_validate(data)
                return validated.model_dump_json()
            except Exception as e:
                logger.debug(f"Could not coerce fenced JSON candidate for {self.name}: {e}")
        return None

    def _sanitize_structured_event(self, event: Any, tracker: Any = None) -> None:
        """Normalizes model text parts to valid schema JSON before ADK processes output_schema."""
        if not self._is_final_model_text_event(event):
            return

        non_thought_parts = [
            p
            for p in event.content.parts
            if getattr(p, "text", None) and not getattr(p, "thought", False)
        ]
        raw_text = "".join(p.text for p in non_thought_parts).strip()
        if not raw_text:
            return

        coerced_json = self._coerce_to_schema_json(raw_text)
        if coerced_json is not None:
            non_thought_parts[0].text = coerced_json
            for extra_part in non_thought_parts[1:]:
                extra_part.text = ""
            return

        schema_name = getattr(self.output_schema, "__name__", str(self.output_schema))
        logger.warning(
            f"Agent {self.name} returned non-JSON text instead of {schema_name}; suppressing crash."
        )
        for part in non_thought_parts:
            part.text = ""

    async def run_async(self, parent_context: InvocationContext):
        tracker = getattr(parent_context.session, "state", {}).get("usage_tracker")
        async for event in super().run_async(parent_context):
            if tracker:
                tracker.track_event(event, agent_name=self.name)
            if self.output_schema:
                self._sanitize_structured_event(event, tracker)
            yield event
