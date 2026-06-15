# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import json
import os
import sys
from google.cloud import storage
from utilities.logger import logger

def _upload_to_gcs(bucket_name: str, run_dir: str, destination_prefix: str):
    """Uploads the files in the scan run directory to Google Cloud Storage."""
    logger.write(f"Connecting to GCS Bucket: {bucket_name}.")

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    for root, _, files in os.walk(run_dir):
        for file in files:
            local_file_path = os.path.join(root, file)
            # Resolve path relative to target run directory
            rel_path = os.path.relpath(local_file_path, run_dir)
            blob_name = f"{destination_prefix}/{rel_path}"

            logger.write(
                f"Uploading {rel_path} -> gs://{bucket_name}/{blob_name}", stdout=False
            )

            blob = bucket.blob(blob_name)
            blob.upload_from_filename(local_file_path)


def upload_run_to_gcs(
    run_dir: str, repo_name: str, job_name: str, run_id_dir: str
):
    """Checks for storage configs and triggers the GCS bucket uploads."""
    gcs_bucket = os.environ.get("CLOUD_STORAGE_BUCKET")

    if not gcs_bucket:
        logger.error(
            "GCS upload required but CLOUD_STORAGE_BUCKET environment variable is not set."
        )
        sys.exit(1)

    destination_prefix = f"v0/{repo_name}/{job_name.replace(' ', '_')}/run_{run_id_dir}"

    try:
        _upload_to_gcs(gcs_bucket, run_dir, destination_prefix)
        logger.success("GCS upload completed successfully.")
    except Exception as e:
        logger.error(f"GCS upload failed: {e}.")


def upload_dashboard_to_gcs():
    """Downloads GCS run reports in memory, compiles the dashboard, and uploads it back to GCS."""
    from utilities import dashboard
    gcs_bucket = os.environ.get("CLOUD_STORAGE_BUCKET")

    if not gcs_bucket:
        logger.error(
            "GCS upload required but CLOUD_STORAGE_BUCKET environment variable is not set."
        )
        sys.exit(1)

    logger.write(f"Generating GCS dashboard.")
    
    try:
        client = storage.Client()
        bucket = client.bucket(gcs_bucket)
        blobs = bucket.list_blobs(prefix="v0/")
        
        # Structure remote runs
        remote_runs = {}
        for blob in blobs:
            # Look for vulnerabilities.json files
            if not blob.name.endswith("vulnerabilities.json"):
                continue
            
            # Extract path hierarchy: v0/{project}/{job}/run_{run_id}/vulnerabilities.json
            parts = blob.name.split("/")
            if len(parts) < 5:
                continue
                
            project_name = parts[1]
            job_name = parts[2]
            run_name = parts[3]
            
            run_key = f"{project_name}-{job_name}-{run_name}"
            remote_runs[run_key] = {
                "project": project_name,
                "job": job_name,
                "run": run_name,
                "report_blob": blob,
                "metadata_blob_name": f"v0/{project_name}/{job_name}/{run_name}/metadata.json"
            }
            
        scan_data = {}
        logger.write(f"Parsing {len(remote_runs)} remote run reports in memory...", stdout=False)
        for run_key, run_info in remote_runs.items():
            try:
                # 1. Download and parse GCS vulnerabilities.json (contains history)
                full_vulnerabilities = json.loads(run_info["report_blob"].download_as_text())
                
                # Filter for OPEN findings
                open_findings = [v for v in full_vulnerabilities if v.get("status") == "Open"]
                report_data = {"vulnerabilities": open_findings}
                
                # 2. Download and parse metadata if present
                metadata = {}
                meta_blob = bucket.blob(run_info["metadata_blob_name"])
                if meta_blob.exists():
                    metadata = json.loads(meta_blob.download_as_text())
                    
                # 3. Format scan data
                scan_data[run_key] = dashboard.format_scan_data(
                    run_info["project"], run_info["job"], run_info["run"], report_data, metadata, full_vulnerabilities
                )
            except Exception as e:
                logger.write(f"Warning: Failed to parse GCS run {run_key}: {e}", stdout=False)

        if not scan_data:
            logger.write("No valid GCS scan reports found. GCS dashboard not compiled.")
            return

        # 4. Compile HTML pages and upload to GCS (MPA)
        templates_dir = Path(__file__).parent / "templates"
        
        # Upload CSS & JS assets
        with open(templates_dir / "dashboard.css", "r", encoding="utf-8") as f:
            bucket.blob("v0/dashboard.css").upload_from_string(f.read(), content_type="text/css")
        with open(templates_dir / "dashboard.js", "r", encoding="utf-8") as f:
            bucket.blob("v0/dashboard.js").upload_from_string(f.read(), content_type="application/javascript")

        # Compile listings
        project_stats = dashboard.compute_project_stats(scan_data)
        projects_list = sorted(list(project_stats.items()))
        runs_list = sorted(list(scan_data.values()), key=lambda x: x["timestamp"], reverse=True)
        sidebar_html = dashboard.render_sidebar(projects_list, runs_list)

        # Upload Global Overview
        with open(templates_dir / "view_global.html.tpl", "r", encoding="utf-8") as f:
            global_content = f.read()
        summary_rows = dashboard.render_projects_summary_table(projects_list)
        global_content = global_content.replace("{{projects_summary_rows}}", summary_rows)
        
        sankey_all = dashboard.get_sankey_rows(list(scan_data.values()))
        sankey_no_tests = dashboard.get_sankey_rows([r for r in scan_data.values() if r["project"] != "tests"])
        global_page_data = {
            "type": "global",
            "sankeyRowsAll": sankey_all,
            "sankeyRowsNoTests": sankey_no_tests
        }
        global_html = dashboard.compile_page(sidebar_html, global_content, global_page_data, "menu-overview", templates_dir)
        bucket.blob("v0/dashboard.html").upload_from_string(global_html, content_type="text/html")

        # Upload Projects
        project_vulns = {}
        for r in scan_data.values():
            proj_name = r["project"]
            if proj_name not in project_vulns:
                project_vulns[proj_name] = []
            run_id_key = f"{r['project']}-{r['job_folder']}-{r['run_folder']}"
            formatted_for_project = dashboard.format_findings(r["findings"], run_id_key, r["timestamp"])
            project_vulns[proj_name].extend(formatted_for_project)

        with open(templates_dir / "view_project.html.tpl", "r", encoding="utf-8") as f:
            project_tpl = f.read()
            
        for proj_name, findings in project_vulns.items():
            proj_content = project_tpl.replace("{{project_name}}", proj_name)
            proj_runs = [r for r in scan_data.values() if r["project"] == proj_name]
            proj_sankey = dashboard.get_sankey_rows(proj_runs)
            
            proj_page_data = {
                "type": "project",
                "sankeyRows": proj_sankey,
                "findings": findings
            }
            proj_html = dashboard.compile_page(sidebar_html, proj_content, proj_page_data, f"menu-project-{proj_name}", templates_dir)
            bucket.blob(f"v0/project_{proj_name}.html").upload_from_string(proj_html, content_type="text/html")

        # Upload Runs
        with open(templates_dir / "view_job.html.tpl", "r", encoding="utf-8") as f:
            run_tpl = f.read()

        for run_id, r in scan_data.items():
            run_content = run_tpl
            run_content = run_content.replace("{{job_name}}", r["name"])
            run_content = run_content.replace("{{project_name}}", r["project"])
            run_content = run_content.replace("{{model_name}}", r["model"])
            run_content = run_content.replace("{{commit_hash_short}}", r["commit"][:8])
            run_content = run_content.replace("{{run_folder}}", r["run_folder"])
            run_content = run_content.replace("{{timestamp}}", r["timestamp"])
            
            run_sankey = dashboard.get_sankey_rows([r])
            run_page_data = {
                "type": "run",
                "sankeyRows": run_sankey,
                "findings": r["findings"]
            }
            run_html = dashboard.compile_page(sidebar_html, run_content, run_page_data, f"menu-run-{run_id}", templates_dir)
            bucket.blob(f"v0/run_{run_id}.html").upload_from_string(run_html, content_type="text/html")

        logger.success(f"GCS dashboard uploaded successfully (MPA).")
    except Exception as e:
        logger.error(f"Warning: Failed to generate and upload GCS dashboard: {e}.")
