// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap};
use wasm_bindgen::prelude::*;

/// List of currently supported schema versions in Mjolnir core
pub const SUPPORTED_SCHEMAS: &[&str] = &["v1"];

#[wasm_bindgen]
pub fn get_supported_schemas() -> String {
    serde_json::to_string(SUPPORTED_SCHEMAS).unwrap_or_else(|_| "[\"v1\"]".to_string())
}

/// Schema V1 definition for Mjolnir Vulnerability Findings
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq, Default)]
pub struct VulnerabilityV1 {
    pub title: Option<String>,
    pub severity: Option<String>,
    pub location: Option<String>,
    pub description: Option<String>,
    pub recommendation: Option<String>,
    pub file: Option<String>,
    pub status: Option<String>,
    pub rule_id: Option<String>,
}

/// Schema V1 Metadata definition
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct RunMetadataV1 {
    pub repo: Option<String>,
    pub model: Option<String>,
    pub target_commit: Option<String>,
    pub timestamp: Option<String>,
    pub mode: Option<String>,
    pub pr: Option<String>,
    pub trigger: Option<String>,
    #[serde(default = "default_schema_version")]
    pub schema_version: String,
}

fn default_schema_version() -> String {
    "v1".to_string()
}

/// Unified presentation item - Decouples UI rendering from underlying schema versions.
/// All frontend views (tables, Sankey flow, filters) render this normalized model.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub struct NormalizedVulnerability {
    pub title: String,
    pub severity: String,
    pub location: String,
    pub description: String,
    pub recommendation: String,
    pub file: String,
    pub status: String,
    pub rule_id: String,
    pub schema_version: String,
}

impl From<VulnerabilityV1> for NormalizedVulnerability {
    fn from(v: VulnerabilityV1) -> Self {
        Self {
            title: v
                .title
                .unwrap_or_else(|| "Untitled Security Finding".to_string()),
            severity: v
                .severity
                .unwrap_or_else(|| "LOW".to_string())
                .to_uppercase(),
            location: v.location.unwrap_or_default(),
            description: v.description.unwrap_or_default(),
            recommendation: v.recommendation.unwrap_or_default(),
            file: v.file.unwrap_or_default(),
            status: v.status.unwrap_or_else(|| "Open".to_string()),
            rule_id: v.rule_id.unwrap_or_default(),
            schema_version: "v1".to_string(),
        }
    }
}

#[derive(Serialize, Deserialize, Debug, Clone, Default, PartialEq, Eq)]
pub struct RunIdentifiers {
    pub project: String,
    pub job: String,
    pub run_id: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, Default, PartialEq)]
pub struct VulnerabilityFindings {
    pub findings: Vec<VulnerabilityV1>,
    pub raw_json: String,
}

impl VulnerabilityFindings {
    pub fn new(findings: Vec<VulnerabilityV1>, raw_json: String) -> Self {
        Self { findings, raw_json }
    }

    pub fn from_json(raw_json: String) -> Result<Self, serde_json::Error> {
        let findings: Vec<VulnerabilityV1> = serde_json::from_str(&raw_json)?;
        Ok(Self { findings, raw_json })
    }

    pub fn findings(&self) -> &[VulnerabilityV1] {
        &self.findings
    }

    pub fn raw_json(&self) -> &str {
        &self.raw_json
    }

    pub fn is_empty(&self) -> bool {
        self.findings.is_empty()
    }

    pub fn len(&self) -> usize {
        self.findings.len()
    }
}

impl std::ops::Deref for VulnerabilityFindings {
    type Target = [VulnerabilityV1];

    fn deref(&self) -> &Self::Target {
        &self.findings
    }
}

#[derive(Serialize, Deserialize, Debug, Clone, Default)]
pub struct RunSummary {
    pub total: usize,
    pub open: usize,
    pub critical: usize,
    pub high: usize,
    pub medium: usize,
    pub low: usize,
    pub schema_version: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, Default)]
pub struct RunOverviewItem {
    #[serde(default)]
    pub project: String,
    #[serde(default)]
    pub job: String,
    #[serde(default)]
    pub run_id: String,
    #[serde(default)]
    pub timestamp: String,
    #[serde(default)]
    pub pr: Option<String>,
    #[serde(default)]
    pub trigger: Option<String>,
    #[serde(default)]
    pub vuln_count: usize,
    #[serde(default)]
    pub critical_count: Option<usize>,
    #[serde(default)]
    pub high_count: Option<usize>,
    #[serde(default)]
    pub medium_count: Option<usize>,
    #[serde(default)]
    pub low_count: Option<usize>,
    #[serde(default)]
    pub open_count: Option<usize>,
    #[serde(default)]
    pub closed_count: Option<usize>,
    #[serde(default)]
    pub vulnerabilities: Vec<serde_json::Value>,
    #[serde(default = "default_schema_version")]
    pub schema_version: String,
}

/// Parses and normalizes input JSON findings
fn parse_vulnerabilities(vulnerabilities_json: &str) -> Vec<NormalizedVulnerability> {
    if let Ok(v1_list) = serde_json::from_str::<Vec<VulnerabilityV1>>(vulnerabilities_json) {
        return v1_list
            .into_iter()
            .map(NormalizedVulnerability::from)
            .collect();
    }

    if let Ok(json_list) = serde_json::from_str::<Vec<serde_json::Value>>(vulnerabilities_json) {
        return json_list
            .into_iter()
            .map(|val| {
                let title = val
                    .get("title")
                    .and_then(|v| v.as_str())
                    .unwrap_or("Untitled Security Finding")
                    .to_string();
                let severity = val
                    .get("severity")
                    .and_then(|v| v.as_str())
                    .unwrap_or("LOW")
                    .to_uppercase();
                let file = val
                    .get("file")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let location = val
                    .get("location")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let description = val
                    .get("description")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let recommendation = val
                    .get("recommendation")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let status = val
                    .get("status")
                    .and_then(|v| v.as_str())
                    .unwrap_or("Open")
                    .to_string();
                let rule_id = val
                    .get("rule_id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();

                NormalizedVulnerability {
                    title,
                    severity,
                    location,
                    description,
                    recommendation,
                    file,
                    status,
                    rule_id,
                    schema_version: "v1".to_string(),
                }
            })
            .collect();
    }

    Vec::new()
}

#[wasm_bindgen]
pub fn compute_summary(vulnerabilities_json: &str) -> String {
    let vulns = parse_vulnerabilities(vulnerabilities_json);

    let mut summary = RunSummary {
        schema_version: "v1".to_string(),
        ..Default::default()
    };
    summary.total = vulns.len();

    for v in &vulns {
        if v.status.eq_ignore_ascii_case("Open") {
            summary.open += 1;
        }

        match v.severity.as_str() {
            "CRITICAL" => summary.critical += 1,
            "HIGH" => summary.high += 1,
            "MEDIUM" => summary.medium += 1,
            "LOW" => summary.low += 1,
            _ => {}
        }
    }

    serde_json::to_string(&summary).unwrap_or_default()
}

fn severity_rank(sev: &str) -> usize {
    match sev.to_uppercase().as_str() {
        "CRITICAL" => 4,
        "HIGH" => 3,
        "MEDIUM" => 2,
        "LOW" => 1,
        _ => 0,
    }
}

#[wasm_bindgen]
pub fn filter_vulnerabilities(
    vulnerabilities_json: &str,
    query: &str,
    severity_filter: &str,
    status_filter: &str,
    sort_order: &str,
) -> String {
    let vulns = parse_vulnerabilities(vulnerabilities_json);

    let q = query.trim().to_lowercase();
    let sev_target = severity_filter.trim().to_uppercase();
    let status_target = status_filter.trim().to_lowercase();

    let mut filtered: Vec<NormalizedVulnerability> = vulns
        .into_iter()
        .filter(|v| {
            // Status check
            if !status_target.is_empty() && status_target != "all" {
                let v_stat = v.status.to_lowercase();
                if status_target == "closed" || status_target == "resolved" {
                    if v_stat == "open" {
                        return false;
                    }
                } else if v_stat != status_target {
                    return false;
                }
            }

            // Severity check
            if !sev_target.is_empty() && sev_target != "ALL" && v.severity != sev_target {
                return false;
            }

            // Free text query match
            if !q.is_empty() {
                let title_match = v.title.to_lowercase().contains(&q);
                let desc_match = v.description.to_lowercase().contains(&q);
                let file_match = v.file.to_lowercase().contains(&q);
                let loc_match = v.location.to_lowercase().contains(&q);
                if !(title_match || desc_match || file_match || loc_match) {
                    return false;
                }
            }

            true
        })
        .collect();

    match sort_order {
        "sev-asc" => filtered.sort_by_key(|v| severity_rank(&v.severity)),
        "title" => filtered.sort_by(|a, b| a.title.to_lowercase().cmp(&b.title.to_lowercase())),
        "file" => filtered.sort_by(|a, b| a.file.to_lowercase().cmp(&b.file.to_lowercase())),
        _ => filtered.sort_by(|a, b| severity_rank(&b.severity).cmp(&severity_rank(&a.severity))), // default: sev-desc
    }

    serde_json::to_string(&filtered).unwrap_or_else(|_| "[]".to_string())
}

pub fn build_phase_sankey_rows(vulns: &[serde_json::Value]) -> String {
    if vulns.is_empty() {
        return "[]".to_string();
    }

    // 1. Gather all phase_id -> phase_name mapping
    let mut phase_map: BTreeMap<i32, String> = BTreeMap::new();

    for v in vulns {
        if let Some(hist) = v.get("history").and_then(|h| h.as_array()) {
            for h in hist {
                let pid_str = h
                    .get("phase_id")
                    .map(|p| p.to_string().trim_matches('"').to_string())
                    .unwrap_or_default();
                let pname = h
                    .get("phase_name")
                    .and_then(|p| p.as_str())
                    .unwrap_or("Phase")
                    .to_string();
                if let Ok(pid) = pid_str.parse::<i32>() {
                    phase_map.insert(pid, pname);
                }
            }
        }
    }

    let phase_keys: Vec<i32> = phase_map.keys().cloned().collect();
    if phase_keys.len() < 2 {
        return fallback_sankey_rows(vulns);
    }

    // 2. Build node names and count occurrences per node
    let mut node_counts: HashMap<String, usize> = HashMap::new();
    let mut record_bases: Vec<(String, String)> = Vec::new();

    for v in vulns {
        let hist = match v.get("history").and_then(|h| h.as_array()) {
            Some(h) => h,
            None => continue,
        };

        let mut phase_node_names: HashMap<i32, String> = HashMap::new();

        for &p_key in &phase_keys {
            let snap = hist.iter().find(|h| {
                let pid_str = h
                    .get("phase_id")
                    .map(|p| p.to_string().trim_matches('"').to_string())
                    .unwrap_or_default();
                pid_str.parse::<i32>().ok() == Some(p_key)
            });

            if let Some(s) = snap {
                let phase_name = phase_map
                    .get(&p_key)
                    .cloned()
                    .unwrap_or_else(|| format!("Phase {}", p_key));
                let severity = s
                    .get("severity")
                    .and_then(|v| v.as_str())
                    .unwrap_or("Unknown");
                let node_name = if is_closed_status(s) {
                    format!("Phase {}: {} - Closed", p_key, phase_name)
                } else if severity.eq_ignore_ascii_case("Skipped") {
                    format!("Phase {}: {} - Skipped", p_key, phase_name)
                } else {
                    format!("Phase {}: {} - {}", p_key, phase_name, severity)
                };

                phase_node_names.insert(p_key, node_name);
            }
        }

        for i in 0..(phase_keys.len() - 1) {
            let p1 = phase_keys[i];
            let p2 = phase_keys[i + 1];

            if let (Some(base1), Some(base2)) =
                (phase_node_names.get(&p1), phase_node_names.get(&p2))
            {
                *node_counts.entry(base1.clone()).or_insert(0) += 1;
                *node_counts.entry(base2.clone()).or_insert(0) += 1;
                record_bases.push((base1.clone(), base2.clone()));
            }
        }
    }

    if record_bases.is_empty() {
        return fallback_sankey_rows(vulns);
    }

    // 3. Count transition weights
    let mut transitions: HashMap<(String, String), usize> = HashMap::new();

    for (base1, base2) in record_bases {
        let count1 = node_counts.get(&base1).copied().unwrap_or(1);
        let count2 = node_counts.get(&base2).copied().unwrap_or(1);

        let state1 = format!("{} (count: {})", base1, count1);
        let state2 = format!("{} (count: {})", base2, count2);

        *transitions.entry((state1, state2)).or_insert(0) += 1;
    }

    let mut result_rows: Vec<(String, String, usize)> = Vec::new();
    for ((src, dst), weight) in transitions {
        result_rows.push((src, dst, weight));
    }

    result_rows.sort_by_key(|(src, dst, _)| (sankey_rank(dst), sankey_rank(src)));

    serde_json::to_string(&result_rows).unwrap_or_else(|_| "[]".to_string())
}

fn is_closed_status(v: &serde_json::Value) -> bool {
    let status_str = v
        .get("status")
        .and_then(|s| s.as_str())
        .unwrap_or("")
        .to_lowercase();

    status_str == "closed"
}

fn sankey_rank(node_name: &str) -> usize {
    let name_upper = node_name.to_uppercase();
    if name_upper.contains("INFO") {
        1
    } else if name_upper.contains("LOW") {
        2
    } else if name_upper.contains("MEDIUM") {
        3
    } else if name_upper.contains("HIGH") {
        4
    } else if name_upper.contains("CRITICAL") {
        5
    } else if name_upper.contains("CLOSED") {
        6
    } else if name_upper.contains("SKIPPED") {
        7
    } else {
        8
    }
}

fn fallback_sankey_rows(vulns: &[serde_json::Value]) -> String {
    let mut rows: Vec<(String, String, usize)> = Vec::new();
    for v in vulns {
        let file = v
            .get("file")
            .and_then(|f| f.as_str())
            .unwrap_or("Code Unit");
        let sev = v.get("severity").and_then(|s| s.as_str()).unwrap_or("Low");
        let source = if file.contains('/') {
            let parts: Vec<&str> = file.split('/').collect();
            if parts.len() > 2 {
                format!(".../{}", parts[parts.len() - 2..].join("/"))
            } else {
                file.to_string()
            }
        } else {
            file.to_string()
        };

        if is_closed_status(v) {
            rows.push((source, "Closed".to_string(), 1));
        } else {
            rows.push((source, sev.to_string(), 1));
        }
    }
    serde_json::to_string(&rows).unwrap_or_else(|_| "[]".to_string())
}

#[wasm_bindgen]
pub fn compute_sankey_flow(runs_json: &str, hide_tests: bool) -> String {
    let runs: Vec<RunOverviewItem> = match serde_json::from_str(runs_json) {
        Ok(r) => r,
        Err(_) => return "[]".to_string(),
    };

    let mut all_vulns: Vec<serde_json::Value> = Vec::new();

    for r in &runs {
        let p_name = r.project.clone();
        if p_name.is_empty() {
            continue;
        }
        if hide_tests && (p_name == "tests" || p_name.starts_with("test")) {
            continue;
        }

        all_vulns.extend(r.vulnerabilities.clone());
    }

    build_phase_sankey_rows(&all_vulns)
}

#[wasm_bindgen]
pub fn compute_project_sankey_flow(runs_json: &str, target_project: &str) -> String {
    let runs: Vec<RunOverviewItem> = match serde_json::from_str(runs_json) {
        Ok(r) => r,
        Err(_) => return "[]".to_string(),
    };

    let mut all_vulns: Vec<serde_json::Value> = Vec::new();

    for r in &runs {
        if r.project != target_project {
            continue;
        }

        all_vulns.extend(r.vulnerabilities.clone());
    }

    build_phase_sankey_rows(&all_vulns)
}

#[wasm_bindgen]
pub fn compute_run_sankey_flow(vulnerabilities_json: &str) -> String {
    let vulns: Vec<serde_json::Value> =
        serde_json::from_str(vulnerabilities_json).unwrap_or_default();
    build_phase_sankey_rows(&vulns)
}
