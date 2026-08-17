# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

from config import AppConfig
from data.status import Status
import providers.adk.main as adk
import providers.genai.main as genai
import providers.mock.main as mock
from utilities.command import run_command
from utilities.discovery import discover_source_files
from utilities.git import get_diff_files, setup_repository
from utilities.logger import logger, setup_logger
from utilities.metadata import write_metadata
from utilities.threat_model import load_threat_model


def main():
    try:
        _run_orchestrator()
    except SystemExit as e:
        if e.code != 0:
            logger.error("Exited with error!")
        sys.exit(e.code)


def _run_orchestrator():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=False, help="Path to job spec JSON")
    parser.add_argument(
        "--ingest",
        help="Path to report file to ingest. Implicitly triggers report ingestion mode.",
    )
    parser.add_argument(
        "--diff-base",
        help="Base git ref for PR diff mode (e.g. origin/main or commit SHA)",
    )
    parser.add_argument(
        "--diff-head",
        help="Head git ref for PR diff mode",
    )
    args, unknown_args = parser.parse_known_args()

    if not args.spec:
        logger.error("Error: The --spec argument is required.")
        sys.exit(1)

    if not Path(args.spec).exists():
        logger.error(f"Error: Spec file {args.spec} not found!")
        sys.exit(1)

    with open(args.spec, "r") as f:
        spec = json.load(f)

    project = spec.get("project", {})
    job = spec.get("job", {})
    config = spec.get("config", {})

    # Get basic data

    repo_name = project.get("repoName")
    repo_url = project.get("repoUrl")
    repo_ref = job.get("branch") or job.get("tag") or job.get("commit")

    model_name = job.get("model")

    # Create workspace directories

    raw_workspace = config.get("workspaceDir")
    workspace_dir = str(Path(raw_workspace).expanduser().resolve())

    code_dir = str(Path(workspace_dir) / repo_name)
    app_config = AppConfig.from_env(
        code_dir=code_dir,
        workspace_dir=workspace_dir,
    )

    # Load threat model

    threat_model_context = load_threat_model(project.get("threatModel"))

    # Create output directory

    now = datetime.datetime.now()
    timestamp_dir = now.strftime("%Y%m%d_%H%M%S")
    timestamp_pretty = now.strftime("%Y-%m-%d %H:%M:%S")

    run_id = timestamp_dir
    raw_output = config.get("outputDir")
    output_dir = str(Path(raw_output).expanduser().resolve())
    run_dir = str(Path(output_dir) / f"run_{run_id}")
    Path(run_dir).mkdir(parents=True, exist_ok=False)

    log_path = str(Path(run_dir) / "job.log")

    # Initialize Logging

    setup_logger(log_path)

    logger.header("Welcome to Mjolnir!")

    provider_name = job.get("provider")

    # Log execution engine
    logger.info(
        f"Engine: {provider_name.upper()} | Model: {model_name} | Target: {repo_name} ({repo_ref or 'HEAD'})"
    )

    logger.info(f"Setting up repository for {repo_name}.")
    setup_repository(repo_url, code_dir, repo_ref, workspace_dir)

    # File discovery & Ingestion routing
    ingest_path = args.ingest or job.get("ingestionReport")
    diff_base = args.diff_base or job.get("diffBase")
    diff_head = args.diff_head or job.get("diffHead")

    logger.info(f"Writing project metadata.")
    write_metadata(
        run_dir,
        repo_url,
        model_name,
        repo_ref,
        code_dir,
        timestamp_pretty,
        ingest_path=ingest_path,
        diff_base=diff_base,
        auth_mode=(
            "Mock"
            if provider_name == "mock"
            else ("Gemini API Key" if app_config.gemini_api_key else "Vertex AI")
        ),
    )

    # Execute command, if one is provided

    cmd = job.get("cmd")

    if cmd:
        logger.info(f"Recieved override command ({cmd}).")
        run_env = os.environ.copy()
        run_env["MJOLNIR_WORKSPACE"] = workspace_dir
        run_command(
            ["/bin/bash", "-c", cmd],
            cwd=code_dir,
            env=run_env,
        )

    # Ingestion check and File discovery
    allowed_exts = set(job["extensions"])

    if ingest_path:
        logger.info(f"Ingestion Mode enabled. Ingesting report path: {ingest_path}")
        files_to_scan = []
    elif diff_base:
        logger.info(
            f"PR Diff Mode enabled. Fetching changed text files between {diff_base} and {diff_head}."
        )
        raw_diff_files = get_diff_files(code_dir, diff_base, diff_head)
        files_to_scan = [
            f for f in raw_diff_files if Path(f).suffix.lstrip(".").lower() in allowed_exts
        ]
        if files_to_scan:
            logger.info(
                f"Discovered {len(files_to_scan)} changed text files in PR diff to analyze."
            )
        else:
            logger.info(
                f"No changed text files found in PR diff between {diff_base} and {diff_head}. Exiting."
            )
            sys.exit(0)
    else:
        logger.info("Discovery Mode enabled. Looking for files to analyze.")
        files_to_scan = discover_source_files(
            code_dir=code_dir,
            src_dirs=job["srcDirs"],
            extensions=allowed_exts,
            max_files=job.get("maxFiles"),
        )

        if files_to_scan:
            logger.info(f"Discovered {len(files_to_scan)} files to analyze.")
        else:
            logger.info(f"Discovered no files to analyze. Exiting.")
            sys.exit(1)

    # Execute analyis via selected provider

    provider_name = job.get("provider")

    logger.info(f"Executing analysis using {provider_name} provider (model={model_name}).")

    batch_size = job.get("batchSize")

    if provider_name == "mock":
        vulnerabilities, status = mock.run_analysis(
            model_name,
            code_dir,
            files_to_scan,
            threat_model_context,
            run_dir,
            batch_size,
            ingest_path=ingest_path,
        )
    elif provider_name == "genai":
        vulnerabilities, status = genai.run_analysis(
            model_name,
            code_dir,
            files_to_scan,
            threat_model_context,
            run_dir,
            batch_size,
            ingest_path=ingest_path,
        )
    elif provider_name == "adk":
        vulnerabilities, status = adk.run_analysis(
            model_name,
            code_dir,
            files_to_scan,
            threat_model_context,
            run_dir,
            batch_size,
            ingest_path=ingest_path,
            diff_base=diff_base,
            diff_head=diff_head,
        )
    else:
        logger.error(f"Unknown provider: {provider_name}")
        sys.exit(1)

    # Update metadata with status
    metadata_path = Path(run_dir) / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        metadata["status"] = status
        metadata["mode"] = "Ingestion" if ingest_path else ("PR Diff" if diff_base else "Discovery")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    # Write vulnerabilities (all) to disk

    vulnerabilities_path = Path(run_dir) / "vulnerabilities.json"
    with open(vulnerabilities_path, "w") as f:
        json.dump([v.model_dump() for v in vulnerabilities], f, indent=2)

    # Filter to open vulnerabilities and strip history for a clean minimal view

    vulnerabilities_minimal = [v for v in vulnerabilities if v.status == Status.OPEN]

    # Write vulnerabilities (minimal) to disk
    vulnerabilities_minimal_path = Path(run_dir) / "vulnerabilities_minimal.json"
    with open(vulnerabilities_minimal_path, "w") as f:
        json.dump(
            [v.model_dump(exclude={"history"}) for v in vulnerabilities_minimal],
            f,
            indent=2,
        )

    logger.header("Exiting Mjolnir!")
    if status == "Failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
