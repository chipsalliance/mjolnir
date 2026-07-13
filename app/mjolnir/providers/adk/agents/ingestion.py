# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
from google.adk import Agent
from google.adk.agents.run_config import RunConfig
from data.security_report import SecurityReport
from providers.adk.agents.constants import (
    INGESTION_MAX_LLM_CALLS,
    INGESTION_MAX_TOOL_CALLS,
)
from providers.adk.agents.isolated_agent import (
    IsolatedAgent,
    make_tool_budget_callback,
)
from agent_tools.read_file import read_file
from agent_tools.glob import glob


def get_ingestion_agent(model: str) -> Agent:
    """Factory to create an IngestionAgent to parse unstructured reports."""
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompt_path = os.path.join(current_dir, "prompts", "ingestion.md")

    instruction = "You are an expert security report parsing agent.\n\n"
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            instruction = f.read().strip()

    return IsolatedAgent(
        name="IngestionAgent",
        model=model,
        instruction=instruction,
        tools=[read_file, glob],
        output_schema=SecurityReport,
        before_tool_callback=make_tool_budget_callback(INGESTION_MAX_TOOL_CALLS),
        run_config=RunConfig(max_llm_calls=INGESTION_MAX_LLM_CALLS),
    )
