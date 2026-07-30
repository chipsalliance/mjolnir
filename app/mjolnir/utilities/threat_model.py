# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import asyncio
from pathlib import Path

from utilities.logger import logger


def load_threat_model(threat_model_path: str) -> str:
    """Reads project threat model context if defined, returning a formatting prompt section."""
    if not threat_model_path:
        return ""
    path = Path(threat_model_path)
    if not path.exists():
        return ""
    try:
        return f"\n\n=== Project Threat Model ===\n{path.read_text(encoding='utf-8').strip()}"
    except Exception as e:
        logger.error(f"Could not read threat model file {threat_model_path}: {e}.")
        return ""


async def load_threat_model_async(threat_model_path: str) -> str:
    """Reads project threat model context asynchronously if defined."""
    return await asyncio.to_thread(load_threat_model, threat_model_path)
