# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os

from google.adk import Agent
from google.adk.agents.run_config import RunConfig

from google.genai import types

from agent_tools.ast_search import ast_search
from agent_tools.ctags_search import ctags_search
from agent_tools.grep_search import grep_search
from agent_tools.read_file import read_file
from constants import (
    REVIEWER_MAX_LLM_CALLS,
    REVIEWER_MAX_TOOL_CALLS,
)
from data.review_finding import ReviewFinding
from providers.adk.agents.isolated_agent import (
    IsolatedAgent,
    make_tool_budget_callback,
)
from utilities.prompt_loader import prompt_registry


def build_reviewer_instruction(threat_model_context: str = "") -> str:
    """Builds the full, deterministic system instruction for the AdversarialReviewerAgent."""
    fallback_instruction = "Analyze the security audit finding to determine if it is exploitable."
    instruction = prompt_registry.load_prompt("reviewer", fallback=fallback_instruction) + "\n\n"

    if threat_model_context:
        instruction += threat_model_context
    return instruction


def get_reviewer_agent(
    model: str, threat_model_context: str = "", cached_content: str | None = None
) -> Agent:
    """Factory to create a AdversarialReviewerAgent with appropriate prompts, tools, and optional cached content."""
    instruction = build_reviewer_instruction(threat_model_context)
    generate_content_config = (
        types.GenerateContentConfig(cached_content=cached_content) if cached_content else None
    )

    return IsolatedAgent(
        name="AdversarialReviewerAgent",
        model=model,
        instruction=instruction,
        output_schema=ReviewFinding,
        generate_content_config=generate_content_config,
        tools=[read_file, grep_search, ctags_search, ast_search],
        before_tool_callback=make_tool_budget_callback(REVIEWER_MAX_TOOL_CALLS),
        run_config=RunConfig(max_llm_calls=REVIEWER_MAX_LLM_CALLS),
    )
