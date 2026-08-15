// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

use std::path::Path;
use std::process::Command;

/// Executes the GCS deployment script for static web assets
pub fn deploy_gcs_web(root_dir: &Path, flags: &[&str]) {
    let script_path = root_dir.join("scripts/deploy_gcs_web.py");

    let mut args = vec![script_path.to_str().unwrap()];
    args.extend(flags);

    let status = Command::new("python3")
        .args(&args)
        .current_dir(root_dir)
        .status()
        .expect("Failed to execute deploy_gcs_web.py");

    if !status.success() {
        eprintln!("GCS Web Deployment failed.");
        std::process::exit(1);
    }
}

/// Executes the GCS deployment script for scan runs
pub fn deploy_gcs_runs(root_dir: &Path, flags: &[&str]) {
    let script_path = root_dir.join("scripts/deploy_gcs_runs.py");
    let app_dir = root_dir.join("app");

    let mut args = vec![script_path.to_str().unwrap()];
    args.extend(flags);

    let python_path = match std::env::var("PYTHONPATH") {
        Ok(existing) => format!("{}:{}", app_dir.display(), existing),
        Err(_) => app_dir.display().to_string(),
    };

    let status = Command::new("python3")
        .args(&args)
        .env("PYTHONPATH", python_path)
        .current_dir(root_dir)
        .status()
        .expect("Failed to execute deploy_gcs_runs.py");

    if !status.success() {
        eprintln!("GCS Runs Deployment failed.");
        std::process::exit(1);
    }
}
