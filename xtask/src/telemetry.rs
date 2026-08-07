// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

use std::fs;
use std::path::Path;

use crate::scanner::{locate_findings_file, scan_v1_runs};

/// Aggregates token telemetry usage metrics across all scan runs
pub fn get_all_usage(runs_dir: &Path) -> String {
    let runs_json = scan_v1_runs(runs_dir);
    let runs: Vec<serde_json::Value> = serde_json::from_str(&runs_json).unwrap_or_default();

    let mut total_input_tokens: u64 = 0;
    let mut total_output_tokens: u64 = 0;
    let mut total_tokens: u64 = 0;
    let mut model_breakdown: std::collections::HashMap<String, serde_json::Value> =
        std::collections::HashMap::new();

    for r in &runs {
        if let Some(usage) = r.get("usage") {
            if let Some(tot) = usage.get("total") {
                let prompt = tot
                    .get("total_input_tokens")
                    .or(tot.get("prompt_tokens"))
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0);
                let comp = tot
                    .get("total_output_tokens")
                    .or(tot.get("output_tokens"))
                    .or(tot.get("completion_tokens"))
                    .or(tot.get("response_tokens"))
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0);
                let tt = tot
                    .get("total_tokens")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(prompt + comp);

                total_input_tokens += prompt;
                total_output_tokens += comp;
                total_tokens += tt;

                let model = r.get("model").and_then(|m| m.as_str()).unwrap_or("Unknown");
                let entry = model_breakdown.entry(model.to_string()).or_insert_with(|| {
                    serde_json::json!({
                        "model": model,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "runs_count": 0
                    })
                });

                if let Some(obj) = entry.as_object_mut() {
                    let new_inp = obj["input_tokens"].as_u64().unwrap_or(0) + prompt;
                    let new_out = obj["output_tokens"].as_u64().unwrap_or(0) + comp;
                    obj["input_tokens"] = serde_json::json!(new_inp);
                    obj["output_tokens"] = serde_json::json!(new_out);
                    obj["prompt_tokens"] = serde_json::json!(new_inp);
                    obj["completion_tokens"] = serde_json::json!(new_out);
                    obj["total_tokens"] =
                        serde_json::json!(obj["total_tokens"].as_u64().unwrap_or(0) + tt);
                    obj["runs_count"] =
                        serde_json::json!(obj["runs_count"].as_u64().unwrap_or(0) + 1);
                }
            }
        }
    }

    serde_json::json!({
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_prompt_tokens": total_input_tokens,
        "total_completion_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "by_model": model_breakdown.values().collect::<Vec<&serde_json::Value>>(),
        "runs": runs,
    })
    .to_string()
}

/// Reads metadata, vulnerabilities, and token usage for a single run
pub fn get_run_detail(run_folder: &Path) -> String {
    let meta_path = run_folder.join("metadata.json");
    let vuln_path =
        locate_findings_file(run_folder).unwrap_or_else(|| run_folder.join("vulnerabilities.json"));
    let usage_path = run_folder.join("usage.json");

    let meta: serde_json::Value = fs::read_to_string(meta_path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));

    let vulns: serde_json::Value = fs::read_to_string(vuln_path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!([]));

    let usage: serde_json::Value = fs::read_to_string(usage_path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));

    serde_json::json!({
        "metadata": meta,
        "vulnerabilities": vulns,
        "usage": usage,
    })
    .to_string()
}
