# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os

from google.adk import Agent
from google.adk.agents.run_config import RunConfig

from google.genai import types

from agent_tools import format_tool_guidance
from agent_tools.ast_search import ast_search
from agent_tools.ctags_search import ctags_search
from agent_tools.glob import glob
from agent_tools.grep_search import grep_search
from agent_tools.project_expert import ask_project_expert
from agent_tools.read_file import read_file
from constants import REVIEWER_MAX_LLM_CALLS
from data.review_finding import ReviewFinding
from providers.adk.agents.isolated_agent import IsolatedAgent
from utilities.prompt_loader import prompt_registry

REVIEWER_TOOLS = [ctags_search, ast_search, grep_search, glob, read_file]


def get_reviewer_tools(enable_project_expert: bool = True) -> list:
    """Builds the toolset for AdversarialReviewerAgent, appending optional capability tools as enabled."""
    tools = list(REVIEWER_TOOLS)
    if enable_project_expert:
        tools.append(ask_project_expert)
    return tools


POC_EVALUATION_GUIDANCE = (
    "\n\n## Proof-of-Concept (PoC) Verification Mode (Final Review)\n"
    "A candidate Proof-of-Concept (`poc`) has been generated for this finding. In addition to "
    "your standard adversarial triage, critically evaluate the provided `poc`:\n"
    "1. Verify whether the PoC exercises a realistic, reachable entry point and respects hardware/firmware constraints.\n"
    "2. Confirm whether the PoC genuinely triggers the claimed vulnerability rather than mocking or bypassing target defenses.\n"
    "3. Incorporate your assessment of the PoC's validity into your `verdict`, `severity`, and `justification`.\n"
)


def build_reviewer_instruction(
    threat_model_context: str = "",
    project_expert_summary: str = "",
    evaluate_poc: bool = False,
    tools: list | None = None,
) -> str:
    """Builds the full, deterministic system instruction for the AdversarialReviewerAgent."""
    active_tools = tools if tools is not None else get_reviewer_tools()
    raw_prompt = prompt_registry.load_prompt("reviewer")
    instruction = raw_prompt.replace("{tool_guidance}", format_tool_guidance(active_tools)) + "\n\n"

    if evaluate_poc:
        instruction += POC_EVALUATION_GUIDANCE

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
    evaluate_poc: bool = False,
    enable_project_expert: bool = True,
) -> Agent:
    """Factory to create an AdversarialReviewerAgent for Initial Review (static) or Final Review (with PoC)."""
    tools = get_reviewer_tools(enable_project_expert=enable_project_expert)
    instruction = build_reviewer_instruction(
        threat_model_context,
        project_expert_summary,
        evaluate_poc=evaluate_poc,
        tools=tools,
    )
    generate_content_config = (
        types.GenerateContentConfig(cached_content=cached_content) if cached_content else None
    )

    return IsolatedAgent(
        name="AdversarialReviewerAgent",
        model=model,
        instruction=instruction,
        output_schema=ReviewFinding,
        generate_content_config=generate_content_config,
        tools=tools,
        run_config=RunConfig(max_llm_calls=REVIEWER_MAX_LLM_CALLS),
    )
