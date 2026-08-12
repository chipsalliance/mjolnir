# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os

from google.adk import Agent
from google.adk.agents.run_config import RunConfig

from agent_tools.glob import glob
from agent_tools.read_file import read_file
from data.security_report import SecurityReport
from constants import (
    INGESTION_MAX_LLM_CALLS,
    INGESTION_MAX_TOOL_CALLS,
)

from providers.adk.agents.isolated_agent import (
    IsolatedAgent,
    make_tool_budget_callback,
)
from utilities.prompt_loader import prompt_registry


def get_ingestion_agent(model: str) -> Agent:
    """Factory to create an IngestionAgent to parse unstructured reports."""
    fallback_instruction = "You are an expert security report parsing agent."
    instruction = prompt_registry.load_prompt("ingestion", fallback=fallback_instruction)

    return IsolatedAgent(
        name="IngestionAgent",
        model=model,
        instruction=instruction,
        tools=[read_file, glob],
        output_schema=SecurityReport,
        before_tool_callback=make_tool_budget_callback(INGESTION_MAX_TOOL_CALLS),
        run_config=RunConfig(max_llm_calls=INGESTION_MAX_LLM_CALLS),
    )
