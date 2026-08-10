// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

use std::fs;
use std::path::{Path, PathBuf};

#[derive(Default, Debug)]
pub struct FindingCounts {
    pub total: usize,
    pub critical: usize,
    pub high: usize,
    pub medium: usize,
    pub low: usize,
    pub open: usize,
    pub closed: usize,
}

/// Parses a findings JSON array and calculates severity/status metrics
pub fn parse_finding_counts(content: &str) -> FindingCounts {
    let mut counts = FindingCounts::default();
    let Ok(items) = serde_json::from_str::<Vec<serde_json::Value>>(content) else {
        return counts;
    };

    counts.total = items.len();
    for item in items {
        let status = item
            .get("status")
            .or(item.get("state"))
            .and_then(|s| s.as_str())
            .unwrap_or("Open");

        if status.eq_ignore_ascii_case("Open") {
            counts.open += 1;
            let sev = item
                .get("severity")
                .or(item.get("severity_level"))
                .and_then(|s| s.as_str())
                .unwrap_or("LOW")
                .to_uppercase();

            match sev.as_str() {
                "CRITICAL" => counts.critical += 1,
                "HIGH" => counts.high += 1,
                "MEDIUM" => counts.medium += 1,
                _ => counts.low += 1,
            }
        } else {
            counts.closed += 1;
        }
    }

    counts
}

/// Locates vulnerabilities.json or finding_phase_1.json within a run directory
pub fn locate_findings_file(run_dir: &Path) -> Option<PathBuf> {
    let vulns = run_dir.join("vulnerabilities.json");
    if vulns.exists() {
        return Some(vulns);
    }
    let phase1 = run_dir.join("finding_phase_1.json");
    if phase1.exists() {
        return Some(phase1);
    }
    None
}

/// Parses a single run directory into a structured JSON summary
fn parse_run_directory(
    proj_name: &str,
    job_name: &str,
    run_id: &str,
    run_path: &Path,
) -> Option<serde_json::Value> {
    let vuln_file = locate_findings_file(run_path);
    let (counts, vulns_val) = if let Some(ref path) = vuln_file {
        if let Ok(content) = fs::read_to_string(path) {
            let counts = parse_finding_counts(&content);
            let val = serde_json::from_str(&content).unwrap_or(serde_json::json!([]));
            (counts, val)
        } else {
            (FindingCounts::default(), serde_json::json!([]))
        }
    } else {
        (FindingCounts::default(), serde_json::json!([]))
    };

    let meta: serde_json::Value = fs::read_to_string(run_path.join("metadata.json"))
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));

    let token_usage: serde_json::Value = fs::read_to_string(run_path.join("token_usage.json"))
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));

    let tool_usage: serde_json::Value = fs::read_to_string(run_path.join("tool_usage.json"))
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));

    let timestamp = meta
        .get("timestamp")
        .and_then(|t| t.as_str())
        .unwrap_or(run_id)
        .to_string();

    let model = meta
        .get("model")
        .and_then(|m| m.as_str())
        .unwrap_or("Unknown")
        .to_string();
    let commit = meta
        .get("target_commit")
        .or(meta.get("commit"))
        .and_then(|c| c.as_str())
        .unwrap_or("N/A")
        .to_string();
    let mode = meta
        .get("mode")
        .and_then(|m| m.as_str())
        .unwrap_or("Discovery")
        .to_string();
    let status = meta
        .get("status")
        .and_then(|s| s.as_str())
        .unwrap_or("Success")
        .to_string();
    let total_tokens = token_usage
        .get("total")
        .and_then(|t| t.get("total_tokens"))
        .and_then(|v| v.as_u64())
        .unwrap_or(0);

    Some(serde_json::json!({
        "project": proj_name,
        "job": job_name,
        "run_id": run_id,
        "timestamp": timestamp,
        "vuln_count": counts.total,
        "critical_count": counts.critical,
        "high_count": counts.high,
        "medium_count": counts.medium,
        "low_count": counts.low,
        "open_count": counts.open,
        "closed_count": counts.closed,
        "vulnerabilities": vulns_val,
        "model": model,
        "commit": commit,
        "mode": mode,
        "status": status,
        "total_tokens": total_tokens,
        "token_usage": token_usage,
        "tool_usage": tool_usage,
    }))
}

/// Scans all project and job runs under output/v1/runs/
pub fn scan_v1_runs(runs_dir: &Path) -> String {
    let mut runs = Vec::new();

    if !runs_dir.exists() {
        return "[]".to_string();
    }

    let Ok(proj_entries) = fs::read_dir(runs_dir) else {
        return "[]".to_string();
    };

    for proj_entry in proj_entries.flatten() {
        let proj_path = proj_entry.path();
        if !proj_path.is_dir() {
            continue;
        }
        let proj_name = proj_entry.file_name().to_string_lossy().to_string();

        let Ok(job_entries) = fs::read_dir(&proj_path) else {
            continue;
        };
        for job_entry in job_entries.flatten() {
            let job_path = job_entry.path();
            if !job_path.is_dir() {
                continue;
            }
            let job_name = job_entry.file_name().to_string_lossy().to_string();

            let Ok(run_entries) = fs::read_dir(&job_path) else {
                continue;
            };
            for run_entry in run_entries.flatten() {
                let run_path = run_entry.path();
                if !run_path.is_dir() {
                    continue;
                }
                let run_id = run_entry.file_name().to_string_lossy().to_string();

                if let Some(run_data) =
                    parse_run_directory(&proj_name, &job_name, &run_id, &run_path)
                {
                    runs.push(run_data);
                }
            }
        }
    }

    // Sort by timestamp descending
    runs.sort_by(|a, b| {
        let t1 = a.get("timestamp").and_then(|t| t.as_str()).unwrap_or("");
        let t2 = b.get("timestamp").and_then(|t| t.as_str()).unwrap_or("");
        t2.cmp(t1)
    });

    serde_json::to_string_pretty(&runs).unwrap_or_else(|_| "[]".to_string())
}
