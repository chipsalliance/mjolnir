# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
from typing import Optional
from google.adk import Agent
from google.adk.agents.invocation_context import (
    InvocationContext,
    _InvocationCostManager,
)
from google.adk.agents.run_config import RunConfig


def make_tool_budget_callback(max_tool_calls: int):
    """ADK 2.0 before_tool_callback factory: skips tool execution once max_tool_calls is reached."""

    def callback(tool, args, tool_context) -> Optional[str]:
        ctx = tool_context.get_invocation_context()
        calls = ctx._invocation_cost_manager._number_of_llm_calls
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

    def _create_invocation_context(self, parent_context: InvocationContext) -> InvocationContext:
        ctx = super()._create_invocation_context(parent_context)
        ctx._invocation_cost_manager = _InvocationCostManager()
        if self.run_config:
            ctx.run_config = self.run_config
        return ctx

    async def run_async(self, parent_context: InvocationContext):
        async for event in super().run_async(parent_context):
            yield event
