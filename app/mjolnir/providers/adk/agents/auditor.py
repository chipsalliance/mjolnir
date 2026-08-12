# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import pathlib

from google.adk import Agent
from google.adk.agents.run_config import RunConfig

from google.genai import types

from agent_tools.ast_search import ast_search
from agent_tools.ctags_search import ctags_search
from agent_tools.glob import glob
from agent_tools.grep_search import grep_search
from agent_tools.read_file import read_file
from constants import AUDITOR_MAX_LLM_CALLS
from data.security_report import SecurityReport
from providers.adk.agents.isolated_agent import IsolatedAgent
from utilities.prompt_loader import prompt_registry


def build_auditor_instruction(threat_model_context: str = "") -> str:
    """Builds the full, deterministic system instruction for the AuditorAgent."""
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
    return instruction


def get_auditor_agent(
    model: str, threat_model_context: str = "", cached_content: str | None = None
) -> Agent:
    """Factory to create an AuditorAgent with appropriate system prompts and optional cached content."""
    instruction = build_auditor_instruction(threat_model_context)
    generate_content_config = (
        types.GenerateContentConfig(cached_content=cached_content) if cached_content else None
    )

    return IsolatedAgent(
        name="AuditorAgent",
        model=model,
        instruction=instruction,
        tools=[read_file, glob, grep_search, ctags_search, ast_search],
        output_schema=SecurityReport,
        generate_content_config=generate_content_config,
        run_config=RunConfig(max_llm_calls=AUDITOR_MAX_LLM_CALLS),
    )
