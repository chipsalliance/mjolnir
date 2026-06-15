# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os

from utilities.logger import logger


def load_threat_model(threat_model_path: str) -> str:
    """Reads project threat model context if defined, returning a formatting prompt section."""
    if not threat_model_path or not os.path.exists(threat_model_path):
        return ""
    try:
        with open(threat_model_path, "r", encoding="utf-8") as f:
            return f"\n\n=== Project Threat Model ===\n{f.read().strip()}"
    except Exception as e:
        logger.error(f"Could not read threat model file {threat_model_path}: {e}.")
        return ""
