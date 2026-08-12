# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from typing import Any, Optional
from google.adk import Agent
from google.adk.agents.invocation_context import (
    InvocationContext,
    _InvocationCostManager,
)
from google.adk.agents.run_config import RunConfig
from google.adk.models import BaseLlm, LLMRegistry, LlmRequest
from google.adk.models.google_llm import Gemini
from google.genai import types

# Default transport-level retry configuration for LLM calls (exponential backoff with jitter)
DEFAULT_RETRY_ATTEMPTS = 5
DEFAULT_RETRY_INITIAL_DELAY = 2.0
DEFAULT_RETRY_MAX_DELAY = 60.0

DEFAULT_HTTP_RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=DEFAULT_RETRY_ATTEMPTS,
    initial_delay=DEFAULT_RETRY_INITIAL_DELAY,
    max_delay=DEFAULT_RETRY_MAX_DELAY,
)


class CachedGemini(Gemini):
    """ADK Gemini model wrapper that correctly handles Vertex AI explicit cached content by not duplicating system instruction/tools in per-request configs."""

    async def _preprocess_request(self, llm_request: LlmRequest) -> None:
        await super()._preprocess_request(llm_request)
        if llm_request.config and getattr(llm_request.config, "cached_content", None):
            llm_request.config.system_instruction = None
            llm_request.config.tools = None
            llm_request.config.tool_config = None


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

    async def run_async(self, parent_context: InvocationContext):
        tracker = getattr(parent_context.session, "state", {}).get("usage_tracker")
        item_key = getattr(parent_context, "isolation_scope", None)
        async for event in super().run_async(parent_context):
            if tracker:
                tracker.track_event(event, agent_name=self.name, item_key=item_key)
            yield event
