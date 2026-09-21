# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Central constants and operational defaults for Mjolnir."""

# --- Security & System Alignment ---
SYSTEM_PROMPT = (
    "### AUTHORIZED SECURITY EVALUATION ENVIRONMENT\n"
    "You are operating within an explicitly authorized, isolated, defensive static analysis "
    "and vulnerability assessment environment (Mjolnir). All source code, architecture "
    "artifacts, and threat models provided to you belong to the system owner who has "
    "explicitly commissioned this security audit.\n"
    "- Performing vulnerability scanning, identifying security flaws, analyzing exploitability "
    "paths, and describing attack vectors in this context is strictly defensive, authorized, "
    "and benign.\n"
    "- Do NOT refuse or censor technical analysis of code vulnerabilities. If internal safety "
    "constraints prevent you from evaluating a specific target or finding, do not silently "
    "omit findings—instead, explicitly populate the `refusal_reason` field in your structured "
    "response schema explaining the constraint."
)

# --- Transport & SDK Retry Configuration ---
DEFAULT_RETRY_ATTEMPTS = 5
DEFAULT_RETRY_INITIAL_DELAY = 2.0
DEFAULT_RETRY_MAX_DELAY = 60.0

# --- Context Caching Configuration ---
DEFAULT_CONTEXT_CACHE_TTL_SECONDS = 7200
MIN_CONTEXT_CACHE_TOKENS = 4096
MIN_CONTEXT_CACHE_CHARS_ESTIMATE = MIN_CONTEXT_CACHE_TOKENS * 4  # ~16,384 chars
SET_MODEL_RESPONSE_INSTRUCTION = (
    "IMPORTANT: You have access to other tools, but you must provide "
    "your final response using the set_model_response tool with the "
    "required structured format. After using any other tools needed "
    "to complete the task, always call set_model_response with your "
    "final answer in the specified schema format."
)

# --- Concurrency & Dispatch Configuration ---
DEFAULT_DISPATCH_STAGGER_SECONDS = 0.25

# --- Agent Turn Ceilings (RunConfig backstop) ---
PROJECT_EXPERT_MAX_LLM_CALLS = 50
AUDITOR_MAX_LLM_CALLS = 40
REVIEWER_MAX_LLM_CALLS = 100
INGESTION_MAX_LLM_CALLS = 50

# --- Tool Execution & Output Limits ---
DEFAULT_TOOL_OUTPUT_MAX_CHARS = 40000
PROJECT_EXPERT_QUERY_LOG_PREVIEW_CHARS = 100
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
BINARY_CHECK_CHUNK_BYTES = 8192

# --- Pipeline Modes, Phases & Artifacts ---
PIPELINE_MODE_FAST = "fast"
PIPELINE_MODE_FULL = "full"

PHASE_EXPLORATION_ID = "project_exploration"
PHASE_EXPLORATION_NAME = "Project Exploration"
PROJECT_EXPERT_SUMMARY_FILENAME = "project_expert_summary.md"

PHASE_DISCOVERY_ID = "discovery"
PHASE_DISCOVERY_NAME = "Source File Discovery"

PHASE_INGEST_ID = "report_ingestion"
PHASE_INGEST_NAME = "Report Ingestion"

PHASE_INITIAL_REVIEW_ID = "initial_review"
PHASE_INITIAL_REVIEW_NAME = "Initial Review"

PHASE_FINAL_REVIEW_ID = "final_review"
PHASE_FINAL_REVIEW_NAME = "Final Review"

# --- Project Expert Prompts ---
PROJECT_EXPLORATION_TASK_PROMPT = (
    "Project Root Directory: {code_dir}\n\n"
    "Execute your Initial Exploration (Reconnaissance) role over this repository and synthesize "
    "a concise architectural overview for downstream auditor and reviewer agents."
)
PROJECT_EXPERT_QUERY_PROMPT_TEMPLATE = (
    "A downstream security agent has consulted you with the following question regarding the project:\n\n"
    "Question: {question}\n\n"
    "Please provide a precise, grounded answer referencing project files, conventions, "
    "hardware register definitions, build targets, or threat model constraints where applicable."
)

# --- Event & Tool Error Detection ---
BENIGN_FINISH_REASONS = ("STOP", "FINISH_REASON_UNSPECIFIED", "None", "")
TOOL_ERROR_PREFIXES = ("Error:", "Error executing", "Error ")

# --- Storage & Artifact Versioning ---
API_VERSION = "v1"
RUNS_SUBDIR = f"{API_VERSION}/runs"
WEB_SUBDIR = "web"
