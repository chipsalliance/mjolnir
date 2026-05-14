# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Common threat analysis orchestrator utilities.

This module provides shared logic for executing LLM clients to perform
file-based security analyses, handling timeouts/failures, and cleaning TOML
outputs.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import sys
import tomllib

DEFAULT_TIMEOUT_SECS = 600

# The TOML output of the agent's report
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "vuln_report_schema.toml")
try:
    with open(SCHEMA_PATH, "rb") as f:
        VULN_SCHEMA = tomllib.load(f)
except Exception as e:
    print(f"CRITICAL ERROR: Failed to load {SCHEMA_PATH}: {e}")
    sys.exit(1)

KNOWN_KEYS = list(VULN_SCHEMA.keys())


def generate_prompt_schema():
    """Generates the TOML schema block to inject into prompts."""
    lines = ["[[vulnerabilities]]"]
    for key, config in VULN_SCHEMA.items():
        hint = config["hint"]
        if config["multiline"]:
            lines.append(f'{key} = """\n{hint}\n"""')
        else:
            lines.append(f'{key} = "{hint}"')
    return "\n".join(lines)


def generate_fallback_toml(overrides):
    """Generates a schema-compliant TOML block using provided overrides."""
    lines = ["[[vulnerabilities]]"]
    for key, config in VULN_SCHEMA.items():
        val = overrides.get(key, config["default"])

        if config["multiline"] or "\n" in str(val):
            safe_val = str(val).replace('"""', "'''")
            lines.append(f'{key} = """\n{safe_val}\n"""')
        else:
            safe_val = str(val).replace('"', '\\"')
            lines.append(f'{key} = "{safe_val}"')

    return "\n".join(lines) + "\n\n"


def clean_toml_output(stdout):
    """Strips markdown formatting blocks (e.g. ```toml) from output.

    Args:
        stdout: Raw stdout string from the CLI subprocess.

    Returns:
        Cleaned string containing only the inner block, formatted with trailing spacing.
    """
    output_text = stdout.strip()
    if output_text.startswith("```toml"):
        output_text = output_text[7:]
    elif output_text.startswith("```"):
        output_text = output_text[3:]
    if output_text.endswith("```"):
        output_text = output_text[:-3]
    return output_text.strip() + "\n\n"


def format_timeout_error(file_rel_path, timeout_secs):
    """Generates a standard vulnerability record for timeout failures."""
    return generate_fallback_toml(
        {
            KEY_FILE: file_rel_path,
            KEY_TITLE: "Error during analysis: Timeout",
            KEY_SEVERITY: "Informational",
            KEY_LOCATION: "N/A",
            KEY_DESC: f"Job hung and timed out after {timeout_secs}s.",
            KEY_REC: "N/A",
            KEY_VERDICT: "Informational",
        }
    )


def format_process_failure(file_rel_path, error_msg):
    """Generates a standard vulnerability record for process exit failures."""
    return generate_fallback_toml(
        {
            KEY_FILE: file_rel_path,
            KEY_TITLE: "Error during analysis: Process Failure",
            KEY_SEVERITY: "Informational",
            KEY_LOCATION: "N/A",
            KEY_DESC: f"Subprocess failed with error:\n{error_msg}",
            KEY_REC: "N/A",
            KEY_VERDICT: "Informational",
        }
    )


def run_orchestrator(
    src_dir,
    files_list_path,
    output_path,
    system_prompt_path,
    parallel,
    analyze_file_fn,
):
    """Shared orchestration loop that manages parallel workers for threat analysis.

    Args:
        src_dir: The source directory containing the files to analyze.
        files_list_path: Path to a file containing a list of relative file paths to analyze.
        output_path: Path where the generated report will be saved.
        system_prompt_path: Path to a file containing the system prompt for the model.
        parallel: Number of concurrent file analyses to perform.
        analyze_file_fn: Callback function with signature:
            (file_rel_path, file_index, total_files, prompt) -> (file_rel_path, report_chunk, is_warning)
    """
    # Read model prompt
    with open(system_prompt_path, "r") as f:
        prompt = f.read().strip()

    # Ensure output is clean
    with open(output_path, "w") as out_f:
        pass

    # Read the list of files to analyze
    if not os.path.exists(files_list_path):
        print(f"Error: Files list not found at {files_list_path}")
        sys.exit(1)

    with open(files_list_path, "r") as f:
        files_to_analyze = [line.strip() for line in f if line.strip()]

    total_files = len(files_to_analyze)
    print(
        f"Analyzing {total_files} files with {parallel} parallel workers...", flush=True
    )

    results_map = {}
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {
            executor.submit(analyze_file_fn, f, idx + 1, total_files, prompt): f
            for idx, f in enumerate(files_to_analyze)
        }
        for future in as_completed(futures):
            file_rel_path, report_chunk, is_warning = future.result()
            if is_warning and report_chunk:
                print(report_chunk)
            results_map[file_rel_path] = (report_chunk, is_warning)

    with open(output_path, "a") as out_f:
        for file_rel_path in files_to_analyze:
            if file_rel_path in results_map:
                chunk, is_warning = results_map[file_rel_path]
                if not is_warning and chunk:
                    out_f.write(chunk)

    print(f"Analysis complete. Report saved to {output_path}")
