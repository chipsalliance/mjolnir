# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os

from google.adk import Agent
from google.adk.agents.run_config import RunConfig

from agent_tools import format_tool_guidance
from agent_tools.glob import glob
from agent_tools.read_file import read_file
from constants import INGESTION_MAX_LLM_CALLS
from data.security_report import SecurityReport
from providers.adk.agents.isolated_agent import IsolatedAgent
from utilities.prompt_loader import prompt_registry

INGESTION_TOOLS = [glob, read_file]


def get_ingestion_agent(model: str) -> Agent:
    """Factory to create an IngestionAgent to parse unstructured reports."""
    raw_prompt = prompt_registry.load_prompt("ingestion")
    instruction = raw_prompt.replace("{tool_guidance}", format_tool_guidance(INGESTION_TOOLS))

    return IsolatedAgent(
        name="IngestionAgent",
        model=model,
        instruction=instruction,
        tools=list(INGESTION_TOOLS),
        output_schema=SecurityReport,
        run_config=RunConfig(max_llm_calls=INGESTION_MAX_LLM_CALLS),
    )
