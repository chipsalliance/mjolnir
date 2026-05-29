# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Common threat analysis orchestrator utilities.

This module provides shared logic for executing LLM clients to perform
file-based security analyses, handling timeouts/failures, and cleaning JSON
outputs.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import sys
from pydantic import BaseModel, Field
from typing import List

DEFAULT_TIMEOUT_SECS = 600


class Finding(BaseModel):
    file: str = Field(
        default="Unknown",
        description="relative/path/to/file.c",
    )
    title: str = Field(
        default="Untitled Finding",
        description="Vulnerability Title",
    )
    severity: str = Field(
        default="Informational",
        description="Critical|High|Medium|Low|Informational",
    )
    location: str = Field(
        default="N/A",
        description="Line XX or function_name",
    )
    description: str = Field(
        default="No description provided.",
        description="Detailed technical description.",
    )
    recommendation: str = Field(
        default="No recommendation provided.",
        description="Recommended fix.",
    )
    verdict: str = Field(
        default="Informational",
        description="Exploitable|Not Exploitable|False Positive",
    )
    justification: str = Field(
        default="Not explicitly reviewed.",
        description="Detailed explanation.",
    )
    attack_vector: str = Field(
        default="",
        description="Step-by-step description of how to trigger.",
    )


class SecurityReport(BaseModel):
    vulnerabilities: List[Finding] = Field(
        description="List of detected security vulnerabilities"
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

    # Collect all individual findings from each analyzed file's JSON chunk
    all_findings = []
    for file_rel_path in files_to_analyze:
        if file_rel_path in results_map:
            chunk, is_warning = results_map[file_rel_path]
            if not is_warning and chunk:
                try:
                    # Parse each structured file report response
                    data = json.loads(chunk)
                    all_findings.extend(data.get("vulnerabilities", []))
                except Exception as e:
                    print(f"Error parsing JSON chunk for {file_rel_path}: {e}")
                    # Push a fallback structured object
                    finding = Finding(
                        file=file_rel_path,
                        title="Error parsing analysis output",
                        severity="Informational",
                        location="N/A",
                        description=f"Failed to load JSON chunk. Raw: {chunk}",
                        recommendation="N/A",
                        verdict="Informational",
                        justification=str(e),
                        attack_vector="",
                    )
                    all_findings.append(finding.model_dump())

    # Write unified final structured report
    final_report = {"vulnerabilities": all_findings}
    with open(output_path, "w") as out_f:
        json.dump(final_report, out_f, indent=2)

    print(f"Analysis complete. Report saved to {output_path}")
