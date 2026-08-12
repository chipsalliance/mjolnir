# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Central constants and operational defaults for Mjolnir."""

from google.genai import types

# --- Transport & SDK Retry Configuration ---
DEFAULT_RETRY_ATTEMPTS = 5
DEFAULT_RETRY_INITIAL_DELAY = 2.0
DEFAULT_RETRY_MAX_DELAY = 60.0

DEFAULT_HTTP_RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=DEFAULT_RETRY_ATTEMPTS,
    initial_delay=DEFAULT_RETRY_INITIAL_DELAY,
    max_delay=DEFAULT_RETRY_MAX_DELAY,
)

# --- Concurrency & Dispatch Configuration ---
DEFAULT_DISPATCH_STAGGER_SECONDS = 0.25


# --- Agent Turn & Tool Budget Ceilings ---

# Auditor Agent
AUDITOR_MAX_TOOL_CALLS = 20
AUDITOR_MAX_LLM_CALLS = 25

# Adversarial Reviewer Agent
REVIEWER_MAX_TOOL_CALLS = 90
REVIEWER_MAX_LLM_CALLS = 100

# Report Ingestion Agent
INGESTION_MAX_TOOL_CALLS = 40
INGESTION_MAX_LLM_CALLS = 50

# --- Tool Execution & Output Limits ---
DEFAULT_TOOL_OUTPUT_MAX_CHARS = 40000
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
