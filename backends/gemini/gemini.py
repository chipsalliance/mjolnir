# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Gemini Backend Orchestrator.

This script invokes the Gemini CLI using standard GCP credentials/project to analyze either:
1. A list of files in parallel for security threats (Batch Mode).
2. A single file with a custom query/prompt (Single-File Mode).
"""

import argparse
import os

import subprocess
import common

DEFAULT_TIMEOUT_SECS = 600


def resolve_api_env(project, silent=False):
    """Logs the active API mode (if not silent) and returns the resolved environment."""
    env = os.environ.copy()
    is_gemini_api = "GEMINI_API_KEY" in env

    if not silent:
        if is_gemini_api:
            print(
                " -> [API Mode] Public Gemini Developer API (using GEMINI_API_KEY)",
                flush=True,
            )
        else:
            project_id = env.get("GOOGLE_CLOUD_PROJECT", project)
            print(
                f" -> [API Mode] Google Cloud Vertex AI (Project: {project_id or 'default'})",
                flush=True,
            )

    if is_gemini_api:
        env.pop("GOOGLE_CLOUD_PROJECT", None)
    elif project:
        env["GOOGLE_CLOUD_PROJECT"] = project

    return env


def run_single_query(
    input_path,
    output_path,
    system_prompt_path,
    model,
    gemini_bin,
    project,
    timeout_secs,
):
    """Invokes the Gemini CLI on a single input file and writes the output."""
    env = resolve_api_env(project)

    print(
        f" -> Running single query on {input_path} using Gemini ({model})...",
        flush=True,
    )

    with open(system_prompt_path, "r") as f:
        prompt = f.read().strip()

    # Replace the prompt with the keys of the TOML format from common.py
    prompt = prompt.replace(
        "{REPORTING_REQUIREMENTS}", common.generate_reporting_requirements()
    )

    cmd = [
        gemini_bin,
        "--model",
        model,
        "--prompt",
        prompt,
        "--approval-mode",
        "yolo",
        "--skip-trust",
    ]

    code_dir = os.environ.get("CODE_DIR")
    if code_dir:
        cmd.extend(["--include-directories", code_dir])

    with open(input_path, "r") as in_f, open(output_path, "w") as out_f:
        subprocess.run(
            cmd,
            stdin=in_f,
            stdout=out_f,
            env=env,
            cwd=code_dir,
            check=True,
            timeout=timeout_secs,
        )


def run_analysis(
    src_dir,
    files_list_path,
    output_path,
    system_prompt_path,
    model,
    gemini_bin,
    project,
    silent_missing,
    parallel,
    timeout_secs,
):
    """Runs threat analysis on a list of files in parallel using Gemini."""
    base_env = resolve_api_env(project)

    def analyze_single_file(file_rel_path, file_index, total_files, prompt):
        full_path = os.path.join(src_dir, file_rel_path)
        if not os.path.isfile(full_path):
            if not silent_missing:
                return (
                    file_rel_path,
                    f"Warning: Skipping missing file {file_rel_path}",
                    True,
                )
            return file_rel_path, None, True

        print(
            f" -> ({file_index}/{total_files}) Analyzing {file_rel_path}...", flush=True
        )

        env = base_env.copy()

        cmd = [
            gemini_bin,
            "--model",
            model,
            "--prompt",
            prompt,
        ]

        try:
            with open(full_path, "r") as input_f:
                result = subprocess.run(
                    cmd,
                    stdin=input_f,
                    capture_output=True,
                    text=True,
                    env=env,
                    check=True,
                    timeout=timeout_secs,
                )

                report_chunk = common.clean_toml_output(result.stdout)
                return file_rel_path, report_chunk, False
        except subprocess.TimeoutExpired:
            print(
                f"Error analyzing {file_rel_path}: Job hung and timed out after {timeout_secs}s."
            )
            report = common.generate_fallback_toml(
                {
                    "file": file_rel_path,
                    "title": "Error during analysis: Timeout",
                    "description": f"Job hung and timed out after {timeout_secs}s.",
                }
            )
            return file_rel_path, report, False
        except subprocess.CalledProcessError as e:
            print(f"Error analyzing {file_rel_path}: {e.stderr}")
            report = common.generate_fallback_toml(
                {
                    "file": file_rel_path,
                    "title": "Error during analysis: Process Failure",
                    "description": f"Subprocess failed with error:\n{e.stderr}",
                }
            )
            return file_rel_path, report, False
        except Exception as e:
            print(f"CRITICAL: Unexpected error for {file_rel_path}: {e}")
            report = common.generate_fallback_toml(
                {
                    "file": file_rel_path,
                    "title": "Error during analysis: Unexpected Failure",
                    "description": f"Unexpected error occurred:\n{str(e)}",
                }
            )
            return file_rel_path, report, False

    common.run_orchestrator(
        src_dir=src_dir,
        files_list_path=files_list_path,
        output_path=output_path,
        system_prompt_path=system_prompt_path,
        parallel=parallel,
        analyze_file_fn=analyze_single_file,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Gemini analysis on files.")

    # Mode Selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--src", help="Source directory for batch mode")
    group.add_argument("--input", help="Input file path for single query mode")

    parser.add_argument(
        "--files", help="Path to file listing files to analyze (batch mode only)"
    )
    parser.add_argument("--output", required=True, help="Output report path")
    parser.add_argument("--prompt", required=True, help="Path to system prompt file")
    parser.add_argument("--model", required=True, help="Gemini model name")
    parser.add_argument("--gemini-bin", required=True, help="Path to gemini-cli binary")
    parser.add_argument(
        "--silent-missing",
        action="store_true",
        help="Silence missing file warnings (batch mode only)",
    )
    parser.add_argument(
        "--parallel", type=int, default=1, help="Number of parallel workers"
    )
    parser.add_argument("--project", help="Google Cloud Project ID")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECS,
        help="Analysis timeout in seconds",
    )

    args = parser.parse_args()

    if args.input:
        # Single-file mode
        if args.files or args.silent_missing or args.src:
            parser.error(
                "Arguments --files, --silent-missing, and --src are not compatible with --input mode."
            )

        run_single_query(
            input_path=args.input,
            output_path=args.output,
            system_prompt_path=args.prompt,
            model=args.model,
            gemini_bin=args.gemini_bin,
            project=args.project,
            timeout_secs=args.timeout,
        )
    else:
        # Batch mode
        if not args.files:
            parser.error("Argument --files is required for batch mode.")

        run_analysis(
            src_dir=args.src,
            files_list_path=args.files,
            output_path=args.output,
            system_prompt_path=args.prompt,
            model=args.model,
            gemini_bin=args.gemini_bin,
            project=args.project,
            silent_missing=args.silent_missing,
            parallel=args.parallel,
            timeout_secs=args.timeout,
        )
