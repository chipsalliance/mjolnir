# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import argparse
import json
import os
import sys
import datetime
import providers.adk.main as adk
import providers.genai.main as genai
import providers.mock.main as mock
from utilities import upload
from utilities.command import run_command
from utilities.git import setup_repository
from utilities.discovery import discover_source_files
from utilities.threat_model import load_threat_model
from utilities.metadata import write_metadata
from utilities.dashboard import generate_dashboard
from utilities.logger import logger
from data.status import Status


def main():
    try:
        _run_orchestrator()
    except SystemExit as e:
        if e.code != 0:
            logger.error("Exited with error!")
        os._exit(e.code)


def _run_orchestrator():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=False, help="Path to job spec JSON")
    parser.add_argument(
        "--gen-dashboard",
        action="store_true",
        help="Only regenerate dashboard from existing runs without scanning",
    )
    parser.add_argument(
        "--output-dir",
        default="./output/runs",
        help="Default runs directory to compile if spec is missing",
    )
    parser.add_argument(
        "--ingest",
        help="Path to report file to ingest. Implicitly triggers report ingestion mode.",
    )
    args, unknown_args = parser.parse_known_args()

    if args.gen_dashboard:
        output_dir = "./output/runs"
        if args.spec:
            if not os.path.exists(args.spec):
                print(f"Error: Spec file {args.spec} not found!", file=sys.stderr)
                sys.exit(1)
            with open(args.spec, "r") as f:
                spec = json.load(f)
            config = spec.get("config", {})
            raw_output = config.get("outputDir")
            if raw_output:
                output_dir = os.path.abspath(os.path.expanduser(raw_output))
        else:
            output_dir = os.path.abspath(os.path.expanduser(args.output_dir))

        print(f"Compiling dashboard from existing runs in {output_dir}...")
        generate_dashboard(output_dir)
        print("Dashboard generated successfully.")
        return

    if not args.spec:
        print(
            "Error: The --spec argument is required when not in --gen-dashboard mode.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.path.exists(args.spec):
        print(f"Error: Spec file {args.spec} not found!", file=sys.stderr)
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
    workspace_dir = os.path.abspath(os.path.expanduser(raw_workspace))

    code_dir = os.path.join(workspace_dir, repo_name)
    os.environ["CODE_DIR"] = code_dir

    # Load threat model

    threat_model_context = load_threat_model(project.get("threatModel"))

    # Create output directory

    now = datetime.datetime.now()
    timestamp_dir = now.strftime("%Y%m%d_%H%M%S")
    timestamp_pretty = now.strftime("%Y-%m-%d %H:%M:%S")

    run_id = timestamp_dir
    raw_output = config.get("outputDir")
    output_dir = os.path.abspath(os.path.expanduser(raw_output))
    run_dir = os.path.join(output_dir, f"run_{run_id}")
    os.makedirs(run_dir, exist_ok=False)

    log_path = os.path.join(run_dir, "job.log")

    # Initialize Logging

    logger.init(log_path)

    logger.header("Welcome to Mjolnir!")

    logger.write(f"Setting up repository for {repo_name}.")
    setup_repository(repo_url, code_dir, repo_ref, workspace_dir)

    # File discovery & Ingestion routing
    ingest_path = args.ingest or job.get("ingestionReport")

    logger.write(f"Writing project metadata.")
    write_metadata(
        run_dir, repo_url, model_name, repo_ref, code_dir, timestamp_pretty, ingest_path
    )

    # Execute command, if one is provided

    cmd = job.get("cmd")

    if cmd:
        logger.write(f"Recieved override command ({cmd}).")
        run_env = os.environ.copy()
        run_env["MJOLNIR_WORKSPACE"] = workspace_dir
        run_command(
            ["/bin/bash", "-c", cmd],
            cwd=code_dir,
            env=run_env,
        )

    # Ingestion check and File discovery

    if ingest_path:
        logger.write(f"Ingestion Mode enabled. Ingesting report path: {ingest_path}")
        files_to_scan = []
    else:
        logger.write(f"Discovery Mode enabled. Looking for files to analyze.")
        files_to_scan = discover_source_files(code_dir, job)

        if files_to_scan:
            logger.write(f"Discovered {len(files_to_scan)} files to analyze.")
        else:
            logger.write(f"Discovered no files to analyze. Exiting.")
            sys.exit(1)

    # Execute analyis via selected provider

    provider_name = job.get("provider")

    logger.write(
        f"Executing analysis using {provider_name} provider (model={model_name})."
    )

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
        )
    else:
        logger.error(f"Unknown provider: {provider_name}")
        sys.exit(1)

    # Update metadata with status
    metadata_path = os.path.join(run_dir, "metadata.json")
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        metadata["status"] = status
        metadata["mode"] = "Ingestion" if ingest_path else "Discovery"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    # Write vulnerabilities (all) to disk

    vulnerabilities_path = os.path.join(run_dir, "vulnerabilities.json")
    with open(vulnerabilities_path, "w") as f:
        json.dump([v.model_dump() for v in vulnerabilities], f, indent=2)

    # Filter to open vulnerabilities and strip history for a clean minimal view

    vulnerabilities_minimal = [v for v in vulnerabilities if v.status == Status.OPEN]

    # Write vulnerabilities (minimal) to disk
    vulnerabilities_minimal_path = os.path.join(run_dir, "vulnerabilities_minimal.json")
    with open(vulnerabilities_minimal_path, "w") as f:
        json.dump(
            [v.model_dump(exclude={"history"}) for v in vulnerabilities_minimal],
            f,
            indent=2,
        )

    # Dashboard generation

    logger.write(f"Generating dashboards.")

    generate_dashboard(output_dir)

    # Upload results to Google Cloud Storage

    require_gcs = job.get("requireGcsUpload")

    if require_gcs:
        logger.write(f"Uploading results to GCS.")
        upload.upload_run_to_gcs(run_dir, repo_name, job.get("name"), timestamp_dir)
        upload.upload_dashboard_to_gcs()

    logger.header("Exiting Mjolnir!")
    if status == "Failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
