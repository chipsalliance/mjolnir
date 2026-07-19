# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
from google.adk import Agent
from google.adk.agents.run_config import RunConfig
from data.review_finding import ReviewFinding
from providers.adk.agents.constants import (
    REVIEWER_MAX_LLM_CALLS,
    REVIEWER_MAX_TOOL_CALLS,
)
from providers.adk.agents.isolated_agent import (
    IsolatedAgent,
    make_tool_budget_callback,
)


from agent_tools.read_file import read_file
from agent_tools.ctags_search import ctags_search
from agent_tools.ast_search import ast_search
from agent_tools.grep_search import grep_search


from utilities.prompt_loader import prompt_registry


def get_reviewer_agent(model: str, threat_model_context: str = "") -> Agent:
    """Factory to create a AdversarialReviewerAgent with appropriate prompts and tools."""
    fallback_instruction = (
        "Analyze the security audit finding to determine if it is exploitable."
    )
    instruction = (
        prompt_registry.load_prompt("reviewer", fallback=fallback_instruction) + "\n\n"
    )

    if threat_model_context:
        instruction += threat_model_context

    return IsolatedAgent(
        name="AdversarialReviewerAgent",
        model=model,
        instruction=instruction,
        output_schema=ReviewFinding,
        tools=[read_file, grep_search, ctags_search, ast_search],
        before_tool_callback=make_tool_budget_callback(REVIEWER_MAX_TOOL_CALLS),
        run_config=RunConfig(max_llm_calls=REVIEWER_MAX_LLM_CALLS),
    )
