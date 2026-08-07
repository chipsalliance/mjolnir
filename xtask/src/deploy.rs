// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

use std::path::Path;
use std::process::Command;

/// Executes the GCS deployment script for web assets or run outputs
pub fn deploy_gcs(root_dir: &Path, flags: &[&str]) {
    let script_path = root_dir.join("scripts/deploy_gcs.py");

    let mut args = vec![script_path.to_str().unwrap()];
    args.extend(flags);

    let status = Command::new("python3")
        .args(&args)
        .current_dir(root_dir)
        .status()
        .expect("Failed to execute deploy_gcs.py");

    if !status.success() {
        eprintln!("GCS Deployment failed.");
        std::process::exit(1);
    }
}
