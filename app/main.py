# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Gemini Backend Orchestrator.

This script uses the official Google GenAI SDK to analyze either:
1. A list of files in parallel for security threats (Batch Mode).
2. A single file with a custom query/prompt (Single-File Mode).

It enforces a Pydantic structured response schema matching Mjolnir's JSON output.
All configurations and credentials are passed explicitly as CLI arguments.
"""

import argparse
import os
from google import genai
from google.genai import types
import common
from common import Finding, SecurityReport
import tools
import json

DEFAULT_TIMEOUT_SECS = 600


def update_metadata_tokens(output_path, prompt_tokens, candidate_tokens):
    """Accumulates and saves token usage into metadata.json in the run directory."""
    run_dir = os.path.dirname(output_path)
    metadata_path = os.path.join(run_dir, "metadata.json")

    if not os.path.exists(metadata_path):
        return

    try:
        with open(metadata_path, "r") as f:
            data = json.load(f)

        data["tokens_prompt"] = data.get("tokens_prompt", 0) + prompt_tokens
        data["tokens_candidate"] = data.get("tokens_candidate", 0) + candidate_tokens
        data["tokens_total"] = (
            data.get("tokens_total", 0) + prompt_tokens + candidate_tokens
        )

        with open(metadata_path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not write token metadata: {e}")


def print_grand_total_tokens(output_path):
    """Reads metadata.json and prints the final total E2E token footprint of the job."""
    run_dir = os.path.dirname(output_path)
    metadata_path = os.path.join(run_dir, "metadata.json")

    if not os.path.exists(metadata_path):
        return

    try:
        with open(metadata_path, "r") as f:
            data = json.load(f)

        if "tokens_total" in data:
            print("\n==================================================", flush=True)
            print(f"   Mjolnir Job Complete: E2E Tokens Consumed", flush=True)
            print(f"   - Prompt Tokens:    {data.get('tokens_prompt', 0)}", flush=True)
            print(
                f"   - Candidate Tokens: {data.get('tokens_candidate', 0)}", flush=True
            )
            print(f"   - GRAND TOTAL:      {data.get('tokens_total', 0)}", flush=True)
            print("==================================================\n", flush=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def get_sdk_client(api_key=None, project=None, location=None):
    """Initializes and returns the unified google-genai Client exclusively from parsed CLI parameters."""
    resolved_api_key = (api_key or "").strip()
    resolved_project = (project or "").strip()
    resolved_location = (location or "").strip()

    # Configure robust retry options for both Gemini API and Vertex AI
    # to handle transient errors and rate limits (429)
    retry_options = types.HttpRetryOptions(
        attempts=6,
        initial_delay=2.0,
        max_delay=60.0,
        http_status_codes=[429, 500, 503],
    )
    http_options = types.HttpOptions(retry_options=retry_options)

    if resolved_api_key:
        print(
            " -> [API Mode] Public Gemini Developer API (using explicit API key)",
            flush=True,
        )
        return genai.Client(api_key=resolved_api_key, http_options=http_options)

    print(
        f" -> [API Mode] Google Cloud Vertex AI (Project: {resolved_project}, Location: {resolved_location})",
        flush=True,
    )
    return genai.Client(
        vertexai=True,
        project=resolved_project,
        location=resolved_location,
        http_options=http_options,
    )


# ---------------------------------------------------------------------------
# Execution Modes
# ---------------------------------------------------------------------------


def run_adversarial_reviewer(
    input_path,
    output_path,
    system_prompt_path,
    model,
    api_key=None,
    project=None,
    location=None,
):
    """Invokes the Gemini SDK on a single input file and writes the output."""
    client = get_sdk_client(api_key=api_key, project=project, location=location)

    print(
        f" -> Running single query on {input_path} using Gemini ({model})...",
        flush=True,
    )

    with open(system_prompt_path, "r") as f:
        prompt = f.read().strip()

    with open(input_path, "r") as in_f:
        file_content = in_f.read()

    full_prompt = f"{prompt}\n\nInput Content:\n{file_content}"

    try:
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                tools=[tools.read_file, tools.grep_search, tools.glob_files],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=False,
                    maximum_remote_calls=30,
                ),
            ),
        )

        report_text = ""
        has_text = False
        if response.candidates and response.candidates[0].content:
            parts = response.candidates[0].content.parts or []
            text_parts = [p.text for p in parts if p.text is not None]
            if text_parts:
                report_text = "".join(text_parts)
                has_text = True

        if not has_text:
            candidate = response.candidates[0] if response.candidates else None
            parts = candidate.content.parts if candidate and candidate.content else []
            if parts and parts[0].function_call:
                print(
                    f" [Warning] Adversarial Reviewer hit the maximum tool execution limit (30 turns) and was forced to terminate early.",
                    flush=True,
                )
                report_text = SecurityReport(
                    vulnerabilities=[
                        Finding(
                            file="Pipeline",
                            title="Adversarial Reviewer: Tool execution ceiling reached",
                            severity="Informational",
                            description="The Reviewer agent reached its maximum budget of 30 tool actions and was terminated early to prevent infinite looping.",
                            recommendation="Increase maximum_remote_calls or optimize the system prompt.",
                            verdict="Informational",
                            justification="Execution budget exhausted.",
                        )
                    ]
                ).model_dump_json()
            else:
                print(
                    f" [Error] Model returned an empty response or was blocked by safety settings.",
                    flush=True,
                )
                report_text = SecurityReport(
                    vulnerabilities=[
                        Finding(
                            file="Pipeline",
                            title="Adversarial Reviewer: Empty Response",
                            severity="Informational",
                            description="The model returned an empty text response. This can happen due to active safety filters or API issues.",
                            recommendation="Check GCP Vertex AI logs or adjust prompt guidelines.",
                            verdict="Informational",
                            justification="Empty API output.",
                        )
                    ]
                ).model_dump_json()

        prompt_tokens = (
            response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        )
        candidate_tokens = (
            response.usage_metadata.candidates_token_count
            if response.usage_metadata
            else 0
        )
        update_metadata_tokens(output_path, prompt_tokens, candidate_tokens)

        with open(output_path, "w") as out_f:
            out_f.write(report_text)

        print_grand_total_tokens(output_path)

    except Exception as e:
        print(f"Error running single query: {e}")
        raise e


def run_batch_auditor(
    src_dir,
    files_list_path,
    output_path,
    system_prompt_path,
    model,
    silent_missing,
    parallel,
    api_key=None,
    project=None,
    location=None,
):
    """Runs threat analysis on a list of files in parallel using the Gemini SDK."""
    client = get_sdk_client(api_key=api_key, project=project, location=location)

    import threading

    usage_tracker = {"prompt": 0, "candidate": 0}
    tracker_lock = threading.Lock()

    def analyze_single_file(file_rel_path, file_index, total_files, system_prompt):
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

        try:
            with open(full_path, "r") as input_f:
                file_contents = input_f.read()

            # Instruct model to evaluate the contents of the file
            file_prompt = f"Analyze this file:\n\nFilename: {file_rel_path}\n\nContent:\n{file_contents}"

            response = client.models.generate_content(
                model=model,
                contents=file_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=SecurityReport,
                ),
            )

            if response.usage_metadata:
                with tracker_lock:
                    usage_tracker["prompt"] += (
                        response.usage_metadata.prompt_token_count
                    )
                    usage_tracker["candidate"] += (
                        response.usage_metadata.candidates_token_count
                    )
                print(
                    f"    -> [{file_rel_path}] Tokens: {response.usage_metadata.total_token_count} (Prompt: {response.usage_metadata.prompt_token_count}, Output: {response.usage_metadata.candidates_token_count})",
                    flush=True,
                )

            # Gemini's structured output is guaranteed to be valid JSON conforming to SecurityReport.
            # Return the raw JSON chunk.
            report_text = ""
            has_text = False
            if response.candidates and response.candidates[0].content:
                parts = response.candidates[0].content.parts or []
                text_parts = [p.text for p in parts if p.text is not None]
                if text_parts:
                    report_text = "".join(text_parts)
                    has_text = True

            if not has_text:
                report_text = SecurityReport(
                    vulnerabilities=[
                        Finding(
                            file=file_rel_path,
                            title="Error during analysis: Empty Response / Tool Ceiling",
                            severity="Informational",
                            location="N/A",
                            description="Model returned an empty response or terminated early on a tool call.",
                            recommendation="N/A",
                            verdict="Informational",
                            justification="API returned empty response text.",
                            attack_vector="",
                        )
                    ]
                ).model_dump_json()
            return file_rel_path, report_text, False

        except Exception as e:
            print(f"Error analyzing {file_rel_path}: {e}")
            # Return a structured JSON error record
            report = SecurityReport(
                vulnerabilities=[
                    Finding(
                        file=file_rel_path,
                        title="Error during analysis: SDK Failure",
                        severity="Informational",
                        location="N/A",
                        description=f"Exception raised during SDK call: {e}",
                        recommendation="N/A",
                        verdict="Informational",
                        justification="SDK failed to execute.",
                        attack_vector="",
                    )
                ]
            ).model_dump_json()
            return file_rel_path, report, False

    common.run_orchestrator(
        src_dir=src_dir,
        files_list_path=files_list_path,
        output_path=output_path,
        system_prompt_path=system_prompt_path,
        parallel=parallel,
        analyze_file_fn=analyze_single_file,
    )

    update_metadata_tokens(
        output_path, usage_tracker["prompt"], usage_tracker["candidate"]
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Gemini analysis on files using GenAI Python SDK."
    )

    # Mode Selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--src", help="Source directory for batch mode")
    group.add_argument("--input", help="Input file path for single query mode")

    parser.add_argument(
        "--files", help="Path to file listing files to analyze (batch mode only)"
    )
    parser.add_argument("--output", required=True, help="Output report path")
    parser.add_argument("--prompt", required=True, help="Path to system prompt file")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument(
        "--silent-missing",
        action="store_true",
        help="Silence missing file warnings (batch mode only)",
    )
    parser.add_argument(
        "--parallel", type=int, default=1, help="Number of parallel workers"
    )

    # Explicit credentials and routing flags passed down from Nix
    parser.add_argument("--api-key", help="Gemini Developer API key")
    parser.add_argument("--project", help="Google Cloud Project ID")
    parser.add_argument("--location", help="Google Cloud region/location")

    args = parser.parse_args()

    if args.input:
        # Single-file mode
        if args.files or args.silent_missing or args.src:
            parser.error(
                "Arguments --files, --silent-missing, and --src are not compatible with --input mode."
            )

        run_adversarial_reviewer(
            input_path=args.input,
            output_path=args.output,
            system_prompt_path=args.prompt,
            model=args.model,
            api_key=args.api_key,
            project=args.project,
            location=args.location,
        )
    else:
        # Batch mode
        if not args.files:
            parser.error("Argument --files is required for batch mode.")

        run_batch_auditor(
            src_dir=args.src,
            files_list_path=args.files,
            output_path=args.output,
            system_prompt_path=args.prompt,
            model=args.model,
            silent_missing=args.silent_missing,
            parallel=args.parallel,
            api_key=args.api_key,
            project=args.project,
            location=args.location,
        )
