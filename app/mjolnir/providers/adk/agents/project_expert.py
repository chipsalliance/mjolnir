# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Project Expert Agent definition for ADK."""

from google.adk import Agent
from google.adk.agents.run_config import RunConfig
from google.genai import types

from agent_tools import format_tool_guidance
from agent_tools.ast_search import ast_search
from agent_tools.ctags_search import ctags_search
from agent_tools.glob import glob
from agent_tools.grep_search import grep_search
from agent_tools.read_file import read_file
from constants import (
    PROJECT_EXPERT_MAX_LLM_CALLS,
    PROJECT_EXPERT_MEMORY_ENTRY_TEMPLATE,
    PROJECT_EXPERT_MEMORY_SECTION_TEMPLATE,
    PROJECT_EXPERT_RECON_SECTION_TEMPLATE,
)
from providers.adk.agents.isolated_agent import IsolatedAgent
from utilities.prompt_loader import prompt_registry

PROJECT_EXPERT_TOOLS = [ctags_search, ast_search, grep_search, glob, read_file]


def build_project_expert_instruction(
    threat_model_context: str = "",
    project_summary: str = "",
    qa_history: list[dict[str, str]] | None = None,
    tools: list | None = None,
) -> str:
    """Builds the full system instruction for the ProjectExpertAgent, including accumulated memory."""
    active_tools = tools if tools is not None else PROJECT_EXPERT_TOOLS
    raw_prompt = prompt_registry.load_prompt("project_expert")
    instruction = raw_prompt.replace("{tool_guidance}", format_tool_guidance(active_tools)) + "\n\n"

    if threat_model_context:
        instruction += f"{threat_model_context}\n\n"

    if project_summary:
        instruction += PROJECT_EXPERT_RECON_SECTION_TEMPLATE.format(project_summary=project_summary)

    if qa_history:
        history_entries = [
            PROJECT_EXPERT_MEMORY_ENTRY_TEMPLATE.format(
                idx=idx, question=item["question"], answer=item["answer"]
            )
            for idx, item in enumerate(qa_history, start=1)
            if item.get("question") and item.get("answer")
        ]
        if history_entries:
            instruction += PROJECT_EXPERT_MEMORY_SECTION_TEMPLATE.format(
                history_entries="\n\n".join(history_entries)
            )

    return instruction


def get_project_expert_agent(
    model: str,
    threat_model_context: str = "",
    project_summary: str = "",
    qa_history: list[dict[str, str]] | None = None,
    cached_content: str | None = None,
) -> Agent:
    """Factory to create a ProjectExpertAgent with read-only tools and accumulated project context."""
    instruction = build_project_expert_instruction(
        threat_model_context=threat_model_context,
        project_summary=project_summary,
        qa_history=qa_history,
    )
    generate_content_config = (
        types.GenerateContentConfig(cached_content=cached_content) if cached_content else None
    )

    return IsolatedAgent(
        name="ProjectExpertAgent",
        model=model,
        instruction=instruction,
        generate_content_config=generate_content_config,
        tools=PROJECT_EXPERT_TOOLS,
        run_config=RunConfig(max_llm_calls=PROJECT_EXPERT_MAX_LLM_CALLS),
    )
