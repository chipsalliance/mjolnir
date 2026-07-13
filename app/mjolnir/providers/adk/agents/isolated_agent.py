# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from typing import Optional
from google.adk import Agent
from google.adk.agents.invocation_context import (
    InvocationContext,
    _InvocationCostManager,
)
from google.adk.agents.run_config import RunConfig
from utilities.agent_context import CURRENT_AGENT_RUN


def make_tool_budget_callback(max_tool_calls: int):
    """ADK 2.0 before_tool_callback factory: skips tool execution once max_tool_calls is reached."""

    def callback(tool, args, tool_context) -> Optional[str]:
        ctx = getattr(tool_context, "_invocation_context", None)
        if ctx is None and hasattr(tool_context, "get_invocation_context"):
            ctx = tool_context.get_invocation_context()
        if ctx is None and hasattr(tool_context, "invocation_context"):
            ctx = tool_context.invocation_context
        if ctx is None:
            ctx = CURRENT_AGENT_RUN.get()
        if ctx is None:
            return None
        calls = 0
        if (
            hasattr(ctx, "_invocation_cost_manager")
            and ctx._invocation_cost_manager is not None
        ):
            calls = getattr(ctx._invocation_cost_manager, "_number_of_llm_calls", 0)
        if calls >= max_tool_calls:
            return (
                f"[System Notice: Tool exploration budget reached ({calls}/{max_tool_calls} turns). "
                f"Execution of tool '{tool.name}' was skipped. "
                "Please finalize your analysis right now and emit your structured JSON "
                "conforming to output_schema in your remaining turns.]"
            )
        return None

    return callback


class IsolatedAgent(Agent):
    """An ADK Agent that isolates its LLM call counter and cost manager from the parent workflow session."""

    run_config: Optional[RunConfig] = None

    def _create_invocation_context(
        self, parent_context: InvocationContext
    ) -> InvocationContext:
        ctx = super()._create_invocation_context(parent_context)
        ctx._invocation_cost_manager = _InvocationCostManager()
        if self.run_config:
            ctx.run_config = self.run_config
        CURRENT_AGENT_RUN.set(ctx)
        return ctx

    async def run_async(self, parent_context: InvocationContext):
        ctx = self._create_invocation_context(parent_context)
        token = CURRENT_AGENT_RUN.set(ctx)
        try:
            async for event in super().run_async(parent_context):
                yield event
        finally:
            CURRENT_AGENT_RUN.reset(token)
