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
EXPLOITER_MAX_LLM_CALLS = 150
INGESTION_MAX_LLM_CALLS = 150

# --- Tool Execution & Output Limits ---
DEFAULT_TOOL_OUTPUT_MAX_CHARS = 40000
PROJECT_EXPERT_QUERY_LOG_PREVIEW_CHARS = 100
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
BINARY_CHECK_CHUNK_BYTES = 8192
HARNESS_COMMAND_TIMEOUT_SECONDS = 900
MAX_POC_OUTPUT_EXCERPT_CHARS = 24000
POC_OUTPUT_TRUNCATION_MARKER = "\n...[truncated]...\n"
MAX_POC_DIFF_EXCERPT_CHARS = 24000
POC_DIFF_TRUNCATION_MARKER = "\n...[truncated diff]...\n"
MAX_REVIEW_POC_PROMPT_CHARS = 50000

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
POC_WORKTREES_SUBDIR = "poc_worktrees"
POC_ARTIFACTS_SUBDIR = "poc_artifacts"
CARGO_TARGET_CACHE_SUBDIR = ".cargo_target_cache"
SANDBOX_IGNORED_DIRS = frozenset(
    {
        "target",
        "bazel-bin",
        "bazel-out",
        "bazel-testlogs",
        POC_WORKTREES_SUBDIR,
        POC_ARTIFACTS_SUBDIR,
    }
)
POC_VERIFIED_TRUE_MARKER = "`poc_verified`: `True`"

# --- Worktree Sandbox & Anti-Cheat Gate Constants ---
TEST_DIRECTORY_NAMES = frozenset({"tests", "test", "testing", "spec", "specs", "fuzz", "benches"})

TEST_FILE_SUFFIXES = (
    "_test.rs",
    "_test.go",
    "_test.py",
    "_test.c",
    "_test.cpp",
    "_test.cc",
    "test.rs",
    "test.py",
    "test.go",
    "test.java",
    ".spec.ts",
    ".test.ts",
    ".spec.js",
    ".test.js",
)

BUILD_CONFIGURATION_FILES = frozenset(
    {
        "cargo.toml",
        "cargo.lock",
        "build",
        "build.bazel",
        "cmakelists.txt",
        "makefile",
    }
)

SANDBOX_ALLOWED_ENV_VARS = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "SHELL",
        "LANG",
        "LC_ALL",
        "TERM",
        "TMPDIR",
        "CARGO_HOME",
        "RUSTUP_HOME",
        "GOPATH",
        "GOROOT",
        "CC",
        "CXX",
        "CFLAGS",
        "CXXFLAGS",
        "LDFLAGS",
        "CMAKE_GENERATOR",
        "NIX_BUILD_TOP",
    }
)

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
    "patch_worktree_file": (
        "**`patch_worktree_file` (Targeted Test Patching in Sandbox):** Insert or update a unit "
        "test or harness case in an existing file inside the isolated sandbox by replacing an "
        "exact `target_content` snippet."
    ),
    "write_worktree_file": (
        "**`write_worktree_file` (Create/Write File in Sandbox):** Create or write a standalone "
        "test or harness file inside the isolated sandbox."
    ),
    "run_harness_command": (
        "**`run_harness_command` (Execute Scoped Test Harness in Sandbox):** Compile and run your "
        "synthesized unit test inside the isolated sandbox scoped to the specific target binary "
        "or test filter, and capture its exit status and output."
    ),
    "get_worktree_diff": (
        "**`get_worktree_diff` (Inspect Unified Sandbox Patch):** Retrieve the unified diff of "
        "all touched files in the sandbox to confirm your patch only adds/modifies test harness "
        "code and leaves production logic unmodified."
    ),
    "reset_worktree": (
        "**`reset_worktree` (Revert Sandbox to Baseline):** Discard all edits in the isolated "
        "sandbox and restore the clean baseline if you need to start fresh."
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

POC_CREATION_TASK_PROMPT_TEMPLATE = (
    "Synthesize and execute a Proof-of-Concept (PoC) unit test in your isolated "
    "sandbox to verify the following security finding:\n\n"
    "{finding_payload}"
)
POC_VERIFICATION_STATUS_SECTION_TEMPLATE = (
    "### Verification Status\n"
    "- **Agent Reported `poc_verified`**: `{poc_verified}`\n"
    "- **Worktree Patch Present**: `{patch_present}`\n"
    "- **Harness Commands Executed**: `{commands_executed}`"
)
POC_SYNTHESIZED_OVERVIEW_SECTION_TEMPLATE = "### Synthesized PoC Overview\n{poc}"
POC_PATCH_PRESENT_SECTION_TEMPLATE = (
    "### Ground-Truth Sandbox Patch (Unified Diff)\n```diff\n{actual_diff}\n```"
)
POC_PATCH_EMPTY_SECTION = (
    "### Ground-Truth Sandbox Patch (Unified Diff)\n"
    "`[NO SANDBOX DIFF GENERATED — No files were modified in the sandbox]`"
)
POC_EXECUTION_PRESENT_SECTION_TEMPLATE = (
    "### Ground-Truth Harness Execution\n"
    "- **Command**: `{command}`\n"
    "- **Exit Code**: `{returncode}`\n"
    "```text\n{output}\n```"
)
POC_EXECUTION_EMPTY_SECTION = (
    "### Ground-Truth Harness Execution\n"
    "`[NO HARNESS COMMAND EXECUTED — run_harness_command was never called]`"
)

# --- Event & Tool Error Detection ---
BENIGN_FINISH_REASONS = ("STOP", "FINISH_REASON_UNSPECIFIED", "None", "")
TOOL_ERROR_PREFIXES = ("Error:", "Error executing", "Error ")

# --- Storage & Artifact Versioning ---
API_VERSION = "v1"
RUNS_SUBDIR = f"{API_VERSION}/runs"
WEB_SUBDIR = "web"
