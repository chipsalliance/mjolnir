# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Deduplication agent definition."""

from google.adk import Agent
from google.adk.agents.run_config import RunConfig

from agent_tools import format_tool_guidance
from agent_tools.ast_search import ast_search
from agent_tools.ctags_search import ctags_search
from agent_tools.glob import glob
from agent_tools.grep_search import grep_search
from agent_tools.project_expert import ask_project_expert
from agent_tools.read_file import read_file
from constants import DEDUPLICATOR_MAX_LLM_CALLS, PROJECT_ARCHITECTURE_SECTION_TEMPLATE
from data.deduplication_finding import DeduplicationReport
from providers.adk.agents.isolated_agent import IsolatedAgent
from utilities.prompt_loader import prompt_registry

DEDUPLICATOR_TOOLS = [ctags_search, ast_search, grep_search, glob, read_file]


def get_deduplicator_tools(enable_project_expert: bool = False) -> list:
    """Builds the read-only toolset for DeduplicationAgent, appending optional capability tools as enabled."""
    tools = list(DEDUPLICATOR_TOOLS)
    if enable_project_expert:
        tools.append(ask_project_expert)
    return tools


def build_deduplicator_instruction(
    threat_model_context: str = "",
    project_expert_summary: str = "",
    tools: list | None = None,
) -> str:
    """Builds the instruction for DeduplicationAgent."""
    active_tools = tools if tools is not None else DEDUPLICATOR_TOOLS
    raw_prompt = prompt_registry.load_prompt("deduplicator")
    instruction = raw_prompt.replace("{tool_guidance}", format_tool_guidance(active_tools)) + "\n\n"
    if threat_model_context:
        instruction += threat_model_context
    if project_expert_summary:
        instruction += PROJECT_ARCHITECTURE_SECTION_TEMPLATE.format(
            project_expert_summary=project_expert_summary
        )
    return instruction


def get_deduplicator_agent(
    model: str,
    threat_model_context: str = "",
    project_expert_summary: str = "",
    enable_project_expert: bool = False,
) -> Agent:
    """Builds an isolated DeduplicationAgent returning structured DeduplicationReport."""
    tools = get_deduplicator_tools(enable_project_expert=enable_project_expert)
    instruction = build_deduplicator_instruction(
        threat_model_context=threat_model_context,
        project_expert_summary=project_expert_summary,
        tools=tools,
    )
    return IsolatedAgent(
        name="DeduplicationAgent",
        model=model,
        instruction=instruction,
        tools=tools,
        output_schema=DeduplicationReport,
        run_config=RunConfig(max_llm_calls=DEDUPLICATOR_MAX_LLM_CALLS),
    )
