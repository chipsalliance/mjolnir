# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import json
from typing import Union

from google.adk import Context
from google.adk.workflow import node

from utilities.logger import logger


@node
async def initialize(ctx: Context, node_input: str) -> Union[list[str], str]:
    """Saves global execution configs to session state and returns target files or ingest path."""
    logger.info("Initializing ADK execution parameters...")
    input_data = json.loads(node_input)

    ctx.state["model"] = input_data["model"]
    ctx.state["code_dir"] = input_data["code_dir"]
    ctx.state["threat_model_context"] = input_data["threat_model_context"]
    ctx.state["batch_size"] = input_data["batch_size"]
    ctx.state["run_dir"] = input_data.get("run_dir")

    ingest_path = input_data.get("ingest_path")
    if ingest_path:
        return ingest_path
    return input_data["files"]
