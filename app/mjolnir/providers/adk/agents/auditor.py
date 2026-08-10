# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import pathlib

from google.adk import Agent
from google.adk.agents.run_config import RunConfig

from agent_tools.ast_search import ast_search
from agent_tools.ctags_search import ctags_search
from agent_tools.glob import glob
from agent_tools.grep_search import grep_search
from agent_tools.read_file import read_file
from data.security_report import SecurityReport
from providers.adk.agents.constants import (
    AUDITOR_MAX_LLM_CALLS,
    AUDITOR_MAX_TOOL_CALLS,
)
from providers.adk.agents.isolated_agent import (
    IsolatedAgent,
    make_tool_budget_callback,
)
from utilities.prompt_loader import prompt_registry


def get_auditor_agent(model: str, threat_model_context: str = "") -> Agent:
    """Factory to create an AuditorAgent with appropriate system prompts."""
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fallback_instruction = "Analyze the codebase for vulnerabilities."
    instruction = prompt_registry.load_prompt("auditor", fallback=fallback_instruction) + "\n\n"

    if threat_model_context:
        instruction += threat_model_context

    skills_dir = pathlib.Path(current_dir) / "skills"
    c_skill_path = skills_dir / "c-audit-skill" / "SKILL.md"
    rust_skill_path = skills_dir / "rust-audit-skill" / "SKILL.md"
    if c_skill_path.exists():
        instruction += f"\n\n{c_skill_path.read_text()}\n"
    if rust_skill_path.exists():
        instruction += f"\n\n{rust_skill_path.read_text()}\n"

    return IsolatedAgent(
        name="AuditorAgent",
        model=model,
        instruction=instruction,
        tools=[read_file, glob, grep_search, ctags_search, ast_search],
        output_schema=SecurityReport,
        before_tool_callback=make_tool_budget_callback(AUDITOR_MAX_TOOL_CALLS),
        run_config=RunConfig(max_llm_calls=AUDITOR_MAX_LLM_CALLS),
    )
