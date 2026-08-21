// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

use crate::files::Mjolnir;
use anyhow::{Context, Result};
use std::fs;
use std::path::Path;

pub fn emit_report(output_path: &Path, format: &str) -> Result<()> {
    let run = Mjolnir::default().latest_run()?;
    let vulns = run.vulnerabilities()?;
    let idents = run.resolve_run_identifiers();
    let meta = run.metadata().ok();

    let report_content = vulns.generate_report(&idents, meta.as_ref(), format);

    if let Some(parent) = output_path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)
                .with_context(|| format!("Failed to create directory {}", parent.display()))?;
        }
    }

    fs::write(output_path, report_content)
        .with_context(|| format!("Failed to write report to {}", output_path.display()))?;

    println!("Report successfully emitted to: {}", output_path.display());
    Ok(())
}
