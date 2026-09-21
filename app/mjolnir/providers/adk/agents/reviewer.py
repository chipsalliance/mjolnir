# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os

from google.adk import Agent
from google.adk.agents.run_config import RunConfig

from google.genai import types

from agent_tools.ast_search import ast_search
from agent_tools.ctags_search import ctags_search
from agent_tools.grep_search import grep_search
from agent_tools.project_expert import ask_project_expert
from agent_tools.read_file import read_file
from constants import REVIEWER_MAX_LLM_CALLS
from data.review_finding import ReviewFinding
from providers.adk.agents.isolated_agent import IsolatedAgent
from utilities.prompt_loader import prompt_registry

REVIEWER_TOOLS = [read_file, grep_search, ctags_search, ast_search, ask_project_expert]


def build_reviewer_instruction(
    threat_model_context: str = "", project_expert_summary: str = ""
) -> str:
    """Builds the full, deterministic system instruction for the AdversarialReviewerAgent."""
    instruction = prompt_registry.load_prompt("reviewer") + "\n\n"

    if threat_model_context:
        instruction += threat_model_context

    if project_expert_summary:
        instruction += f"\n\n## Project Architecture Overview (Project Expert Summary)\n\n{project_expert_summary}\n"
    return instruction


def get_reviewer_agent(
    model: str,
    threat_model_context: str = "",
    project_expert_summary: str = "",
    cached_content: str | None = None,
) -> Agent:
    """Factory to create a AdversarialReviewerAgent with appropriate prompts, tools, and optional cached content."""
    instruction = build_reviewer_instruction(threat_model_context, project_expert_summary)
    generate_content_config = (
        types.GenerateContentConfig(cached_content=cached_content) if cached_content else None
    )

    return IsolatedAgent(
        name="AdversarialReviewerAgent",
        model=model,
        instruction=instruction,
        output_schema=ReviewFinding,
        generate_content_config=generate_content_config,
        tools=REVIEWER_TOOLS,
        run_config=RunConfig(max_llm_calls=REVIEWER_MAX_LLM_CALLS),
    )
