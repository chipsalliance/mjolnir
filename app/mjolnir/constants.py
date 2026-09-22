# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Central constants and operational defaults for Mjolnir."""

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
PROJECT_EXPERT_MAX_LLM_CALLS = 150
AUDITOR_MAX_LLM_CALLS = 150
REVIEWER_MAX_LLM_CALLS = 200
INGESTION_MAX_LLM_CALLS = 150

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

PHASE_POC_CREATION_ID = "poc_creation"
PHASE_POC_CREATION_NAME = "PoC Creation"

PHASE_FINAL_REVIEW_ID = "final_review"
PHASE_FINAL_REVIEW_NAME = "Final Review"


# --- Dynamic Tool Guidance Registry ---
TOOL_PROMPT_GUIDANCE: dict[str, str] = {
    "ctags_search": (
        "**`ctags_search` (O(1) Symbol Definitions):** Prefer FIRST whenever you need to jump "
        "directly to the definition `<file>:<line>` of a function, struct, typedef, enum, macro, "
        "or global variable via the pre-built `.git/tags` index."
    ),
    "ast_search": (
        "**`ast_search` (Structural AST Search):** Use `ast-grep` patterns (`$VAR` for single AST "
        "nodes, `$$$ARGS` for variadic arguments) with `lang` (`c`, `rust`, `verilog`) to match "
        "structural code patterns, call shapes, or hardening idioms."
    ),
    "grep_search": (
        "**`grep_search` (Regex / Call-Site Search):** Use `ripgrep` to trace callers, "
        "cross-references, register names, or string literals across files when looking for "
        "usages rather than symbol definitions."
    ),
    "glob": (
        "**`glob` (File Path Discovery):** Use glob patterns (e.g., `*manifest*.h`, `**/epmp*.c`) "
        "to locate related header files, drivers, or module layouts by filename without scanning "
        "file contents."
    ),
    "read_file": (
        "**`read_file` (Scoped Line-Range Reading):** After locating a target `<file>:<line>` via "
        "`ctags_search`, `ast_search`, or `grep_search`, read focused `start_line` and `end_line` "
        "bounds instead of reading entire large files."
    ),
    "ask_project_expert": (
        "**`ask_project_expert` (Architectural & Threat Model Consultation):** Consult the Project "
        "Expert when you need clarification on project-level architectural conventions, "
        "cross-subsystem trust boundaries, hardware/ePMP/OTP guarantees, or whether an omitted "
        "check is intentionally enforced by hardware or an earlier boot stage."
    ),
}

# --- Shared Instruction Section & Task Prompt Templates ---
PROJECT_ARCHITECTURE_SECTION_TEMPLATE = (
    "\n\n## Project Architecture Overview (Project Expert Summary)\n\n{project_expert_summary}\n"
)

PROJECT_EXPERT_RECON_SECTION_TEMPLATE = (
    "## Project-Wide Architectural Summary (Initial Reconnaissance)\n\n{project_summary}\n\n"
)
PROJECT_EXPERT_MEMORY_ENTRY_TEMPLATE = "### Q{idx}: {question}\n**Answer:** {answer}"
PROJECT_EXPERT_MEMORY_SECTION_TEMPLATE = (
    "## Previous Project Expert Consultations (Session Memory)\n"
    "You have already investigated and answered the following questions earlier in this "
    "pipeline run. Reuse these verified findings directly when applicable to avoid "
    "redundant file exploration:\n\n{history_entries}\n\n"
)

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

INGEST_DIR_TASK_PROMPT_TEMPLATE = (
    "Ingestion Target Directory: {full_path}\n\n"
    "This target is a directory. Please use your `glob` and `read_file` tools to discover "
    "and read all report files, spreadsheets, markdown logs, or JSON summaries inside `{full_path}`. "
    "Synthesize every security vulnerability found across these files into your unified SecurityReport output."
)
INGEST_FILE_TASK_PROMPT_TEMPLATE = (
    "Ingestion Target Path: {full_path}\n\n"
    "Please use your `glob` and `read_file` tools to read and inspect `{full_path}` "
    "(whether it is a markdown report, spreadsheet, log, or summary file) and any secondary attachments in `{code_dir}`. "
    "Synthesize every security vulnerability found into your unified SecurityReport output."
)

AUDIT_PR_DIFF_SECTION_TEMPLATE = (
    "\n\n### Pull Request Diff (Changes Under Review):\n```diff\n{file_diff}\n```"
)
AUDIT_PR_DIFF_TASK_PROMPT_TEMPLATE = (
    "Filename: {f_path}\n"
    "Mode: Pull Request Diff Security Review"
    "{diff_section}\n\n"
    "### Full File Content:\n{contents}"
)
AUDIT_FILE_TASK_PROMPT_TEMPLATE = "Filename: {f_path}\n\n### Full File Content:\n{contents}"

REVIEW_TASK_PROMPT_TEMPLATE = "Audit Finding:\n{finding_payload}"
REVIEW_WITH_POC_TASK_PROMPT_TEMPLATE = (
    "### Candidate Vulnerability & History:\n{finding_payload}\n\n"
    "### Generated Proof-of-Concept (PoC) to Verify:\n```\n{poc}\n```"
)

# --- Event & Tool Error Detection ---
BENIGN_FINISH_REASONS = ("STOP", "FINISH_REASON_UNSPECIFIED", "None", "")
TOOL_ERROR_PREFIXES = ("Error:", "Error executing", "Error ")

# --- Storage & Artifact Versioning ---
API_VERSION = "v1"
RUNS_SUBDIR = f"{API_VERSION}/runs"
WEB_SUBDIR = "web"
