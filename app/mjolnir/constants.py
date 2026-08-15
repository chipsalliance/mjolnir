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


# --- Agent Turn Ceilings (RunConfig backstop) ---
AUDITOR_MAX_LLM_CALLS = 25
REVIEWER_MAX_LLM_CALLS = 100
INGESTION_MAX_LLM_CALLS = 50


# --- Tool Execution & Output Limits ---
DEFAULT_TOOL_OUTPUT_MAX_CHARS = 40000
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


# --- Storage & Artifact Versioning ---
API_VERSION = "v1"
RUNS_SUBDIR = f"{API_VERSION}/runs"
WEB_SUBDIR = "web"
