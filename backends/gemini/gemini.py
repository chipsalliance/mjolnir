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
from common import SecurityReport

DEFAULT_TIMEOUT_SECS = 600


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def get_sdk_client(api_key=None, project=None, location=None):
    """Initializes and returns the unified google-genai Client exclusively from parsed CLI parameters."""
    resolved_api_key = (api_key or "").strip()
    resolved_project = (project or "").strip()
    resolved_location = (location or "").strip()

    if resolved_api_key:
        print(
            " -> [API Mode] Public Gemini Developer API (using explicit API key)",
            flush=True,
        )
        return genai.Client(api_key=resolved_api_key)

    print(
        f" -> [API Mode] Google Cloud Vertex AI (Project: {resolved_project}, Location: {resolved_location})",
        flush=True,
    )
    return genai.Client(
        vertexai=True, project=resolved_project, location=resolved_location
    )


# ---------------------------------------------------------------------------
# Execution Modes
# ---------------------------------------------------------------------------


def run_single_query(
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
        )

        with open(output_path, "w") as out_f:
            out_f.write(response.text)

    except Exception as e:
        print(f"Error running single query: {e}")
        raise e


def run_analysis(
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

            # Gemini's structured output is guaranteed to be valid JSON conforming to SecurityReport.
            # Return the raw JSON chunk.
            return file_rel_path, response.text, False

        except Exception as e:
            print(f"Error analyzing {file_rel_path}: {e}")
            # Return a structured JSON error record
            report = f"""{{
  "vulnerabilities": [
    {{
      "file": "{file_rel_path}",
      "title": "Error during analysis: SDK Failure",
      "severity": "Informational",
      "location": "N/A",
      "description": "Exception raised during SDK call: {str(e).replace('"', '\\"')}",
      "recommendation": "N/A",
      "verdict": "Informational",
      "justification": "SDK failed to execute.",
      "attack_vector": ""
    }}
  ]
}}"""
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

        run_single_query(
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

        run_analysis(
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
