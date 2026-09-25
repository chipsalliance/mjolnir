# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Deduplication agent definition."""

from google.adk import Agent
from google.adk.agents.run_config import RunConfig
from google.genai import types

from constants import PROJECT_ARCHITECTURE_SECTION_TEMPLATE
from data.deduplication_finding import DeduplicationReport
from providers.adk.agents.isolated_agent import IsolatedAgent
from utilities.prompt_loader import prompt_registry


def build_deduplicator_instruction(
    threat_model_context: str = "",
    project_expert_summary: str = "",
) -> str:
    """Builds the instruction for DeduplicationAgent."""
    instruction = prompt_registry.load_prompt("deduplicator") + "\n\n"
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
) -> Agent:
    """Builds an isolated DeduplicationAgent returning structured DeduplicationReport."""
    instruction = build_deduplicator_instruction(
        threat_model_context=threat_model_context,
        project_expert_summary=project_expert_summary,
    )
    return IsolatedAgent(
        name="DeduplicationAgent",
        model=model,
        instruction=instruction,
        tools=[],
        run_config=RunConfig(
            max_llm_calls=5,
            response_schema=DeduplicationReport,
            generation_config=types.GenerateContentConfig(
                temperature=0.0,
            ),
        ),
    )
