// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

#![allow(dead_code)]

use anyhow::{bail, Context, Result};
pub use mjolnir_dashboard_wasm::{
    RunIdentifiers, RunMetadataV1 as RunMetadata, VulnerabilityFindings,
};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::SystemTime;

/// Represents a located Mjolnir scan run directory with access to its artifact files
#[derive(Debug, Clone)]
pub struct MjolnirRun {
    pub dir: PathBuf,
    pub mtime: SystemTime,
}

/// Represents a run located in a structured runs directory (`v1/runs/<project>/<job>/<run_id>/`)
#[derive(Debug, Clone)]
pub struct StructuredRun {
    pub identifiers: RunIdentifiers,
    pub run: MjolnirRun,
}

impl MjolnirRun {
    pub const VULNERABILITIES_JSON: &'static str = Mjolnir::VULNERABILITIES_JSON;
    pub const VULNERABILITIES_MINIMAL_JSON: &'static str = Mjolnir::VULNERABILITIES_MINIMAL_JSON;
    pub const METADATA_JSON: &'static str = Mjolnir::METADATA_JSON;

    /// Creates a MjolnirRun instance from a run directory path
    pub fn from_dir(dir: &Path) -> Self {
        let mtime = Self::get_run_mtime(dir);
        Self {
            dir: dir.to_path_buf(),
            mtime,
        }
    }

    /// Checks whether a path directly contains a Mjolnir run
    pub fn is_run_dir(path: &Path) -> bool {
        path.join(Self::VULNERABILITIES_JSON).is_file()
            || path.join(Self::VULNERABILITIES_MINIMAL_JSON).is_file()
    }

    /// Retrieves modification timestamp for the run's primary vulnerability findings file
    pub fn get_run_mtime(dir: &Path) -> SystemTime {
        let vulns = dir.join(Self::VULNERABILITIES_JSON);
        if let Ok(meta) = vulns.metadata() {
            if let Ok(t) = meta.modified() {
                return t;
            }
        }
        let minimal = dir.join(Self::VULNERABILITIES_MINIMAL_JSON);
        if let Ok(meta) = minimal.metadata() {
            if let Ok(t) = meta.modified() {
                return t;
            }
        }
        SystemTime::UNIX_EPOCH
    }

    /// Recursively discovers all Mjolnir scan runs within a directory
    pub fn discover(root_dir: &Path) -> Vec<Self> {
        let mut runs = Vec::new();
        Self::discover_recursive(root_dir, &mut runs);
        runs
    }

    fn discover_recursive(dir: &Path, runs: &mut Vec<Self>) {
        let entries = match fs::read_dir(dir) {
            Ok(e) => e,
            Err(_) => return,
        };

        let mut is_run = false;
        let mut mtime = SystemTime::UNIX_EPOCH;

        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_file() {
                if let Some(file_name) = path.file_name().and_then(|n| n.to_str()) {
                    if file_name == Self::VULNERABILITIES_JSON
                        || file_name == Self::VULNERABILITIES_MINIMAL_JSON
                    {
                        is_run = true;
                        if let Ok(meta) = path.metadata() {
                            if let Ok(t) = meta.modified() {
                                if t > mtime {
                                    mtime = t;
                                }
                            }
                        }
                    }
                }
            } else if path.is_dir() {
                if let Some(dir_name) = path.file_name().and_then(|n| n.to_str()) {
                    if !dir_name.starts_with('.') {
                        Self::discover_recursive(&path, runs);
                    }
                }
            }
        }

        if is_run {
            runs.push(MjolnirRun {
                dir: dir.to_path_buf(),
                mtime,
            });
        }
    }

    /// Reads and deserializes the vulnerabilities findings
    pub fn vulnerabilities(&self) -> Result<VulnerabilityFindings> {
        let full = self.dir.join(Self::VULNERABILITIES_JSON);
        let (raw, path) = if full.is_file() {
            (
                fs::read_to_string(&full)
                    .with_context(|| format!("Failed to read {}", full.display()))?,
                full,
            )
        } else {
            let minimal = self.dir.join(Self::VULNERABILITIES_MINIMAL_JSON);
            if minimal.is_file() {
                (
                    fs::read_to_string(&minimal)
                        .with_context(|| format!("Failed to read {}", minimal.display()))?,
                    minimal,
                )
            } else {
                bail!(
                    "No {} or {} found in run directory: {}",
                    Self::VULNERABILITIES_JSON,
                    Self::VULNERABILITIES_MINIMAL_JSON,
                    self.dir.display()
                );
            }
        };

        VulnerabilityFindings::from_json(raw).with_context(|| {
            format!(
                "Failed to deserialize vulnerabilities from {}",
                path.display()
            )
        })
    }

    /// Reads and deserializes metadata.json in the run directory
    pub fn metadata(&self) -> Result<RunMetadata> {
        let path = self.dir.join(Self::METADATA_JSON);
        if !path.is_file() {
            bail!(
                "No {} found in run directory: {}",
                Self::METADATA_JSON,
                self.dir.display()
            );
        }
        let content = fs::read_to_string(&path)
            .with_context(|| format!("Failed to read {}", path.display()))?;
        serde_json::from_str(&content)
            .with_context(|| format!("Failed to deserialize {}", path.display()))
    }

    /// Resolves the project name, job name, and run identifier
    pub fn resolve_run_identifiers(&self) -> RunIdentifiers {
        let mut proj = String::new();
        let job = String::new();
        let mut run_id = String::new();

        if let Ok(meta) = self.metadata() {
            if let Some(repo) = &meta.repo {
                let clean_repo = repo.trim_end_matches('/').trim_end_matches(".git");
                if let Some(name) = clean_repo.rsplit('/').next() {
                    proj = name.to_string();
                } else {
                    proj = clean_repo.to_string();
                }
            }
            if let Some(ts) = &meta.timestamp {
                run_id = ts.clone();
            }
        }

        if run_id.is_empty() {
            if let Some(dir_name) = self.dir.file_name().and_then(|n| n.to_str()) {
                run_id = dir_name.to_string();
            }
        }

        RunIdentifiers {
            project: proj,
            job,
            run_id,
        }
    }
}

/// Represents a Mjolnir workspace or root directory with access to its runs and assets
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Mjolnir {
    pub root: PathBuf,
}

impl Default for Mjolnir {
    /// Attempts to discover the Mjolnir workspace or root directory, falling back to the current directory
    fn default() -> Self {
        Self::discover()
    }
}

impl Mjolnir {
    /// Standard Mjolnir file and artifact names
    pub const VULNERABILITIES_JSON: &'static str = "vulnerabilities.json";
    pub const VULNERABILITIES_MINIMAL_JSON: &'static str = "vulnerabilities_minimal.json";
    pub const METADATA_JSON: &'static str = "metadata.json";

    /// Creates a new `Mjolnir` workspace instance with the specified root path
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    /// Attempts to discover the Mjolnir workspace or root directory by checking current directory ancestors,
    /// environment variables, or build manifest directory.
    pub fn discover() -> Self {
        if let Ok(root) = Self::find_root() {
            Self::new(root)
        } else {
            Self::new(std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")))
        }
    }

    fn find_root() -> Result<PathBuf> {
        if let Some(env_root) = std::env::var_os("MJOLNIR_ROOT") {
            let p = PathBuf::from(env_root);
            if p.exists() {
                return Ok(p);
            }
        }

        if let Ok(cwd) = std::env::current_dir() {
            for ancestor in cwd.ancestors() {
                if (ancestor.join("xtask").is_dir() && ancestor.join("web").is_dir())
                    || ancestor.join("output/v1/runs").is_dir()
                {
                    return Ok(ancestor.to_path_buf());
                }
            }
        }

        if let Some(manifest) = option_env!("CARGO_MANIFEST_DIR") {
            let manifest_path = Path::new(manifest);
            if let Some(parent) = manifest_path.parent() {
                if (parent.join("xtask").is_dir() && parent.join("web").is_dir())
                    || parent.join("output/v1/runs").is_dir()
                {
                    return Ok(parent.to_path_buf());
                }
            }
        }

        bail!("Could not discover Mjolnir directory");
    }

    /// Finds the newest Mjolnir run in this workspace
    pub fn latest_run(&self) -> Result<MjolnirRun> {
        if !self.root.exists() {
            bail!("Workspace path does not exist: {}", self.root.display());
        }

        if MjolnirRun::is_run_dir(&self.root) {
            return Ok(MjolnirRun::from_dir(&self.root));
        }

        let mut candidates = self.runs();
        if candidates.is_empty() {
            bail!(
                "No {} found under: {}",
                Self::VULNERABILITIES_JSON,
                self.root.display()
            );
        }

        candidates.sort_by(|a, b| b.mtime.cmp(&a.mtime));
        Ok(candidates.remove(0))
    }

    /// Recursively discovers all Mjolnir run directories under this workspace
    pub fn runs(&self) -> Vec<MjolnirRun> {
        MjolnirRun::discover(&self.root)
    }

    /// Discovers all structured runs located under `v1/runs/<project>/<job>/<run_id>/` in this workspace
    pub fn structured_runs(&self) -> Vec<StructuredRun> {
        let mut structured = Vec::new();
        if !self.root.exists() {
            return structured;
        }

        for proj_entry in fs::read_dir(&self.root).into_iter().flatten().flatten() {
            let proj_path = proj_entry.path();
            if !proj_path.is_dir() {
                continue;
            }
            let proj_name = proj_entry.file_name().to_string_lossy().to_string();

            for job_entry in fs::read_dir(&proj_path).into_iter().flatten().flatten() {
                let job_path = job_entry.path();
                if !job_path.is_dir() {
                    continue;
                }
                let job_name = job_entry.file_name().to_string_lossy().to_string();

                for run_entry in fs::read_dir(&job_path).into_iter().flatten().flatten() {
                    let run_path = run_entry.path();
                    if !run_path.is_dir() {
                        continue;
                    }
                    let run_id = run_entry.file_name().to_string_lossy().to_string();
                    let run = MjolnirRun::from_dir(&run_path);
                    if run.metadata().is_ok() || run.vulnerabilities().is_ok() {
                        structured.push(StructuredRun {
                            identifiers: RunIdentifiers {
                                project: proj_name.clone(),
                                job: job_name.clone(),
                                run_id,
                            },
                            run,
                        });
                    }
                }
            }
        }

        structured
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    static TEST_COUNTER: AtomicUsize = AtomicUsize::new(0);

    fn create_test_dir(name: &str) -> PathBuf {
        let count = TEST_COUNTER.fetch_add(1, Ordering::SeqCst);
        let dir = std::env::temp_dir().join(format!(
            "mjolnir_test_{}_{}_{}",
            name,
            std::process::id(),
            count
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn test_vulnerabilities_and_metadata_deserialization() {
        let dir = create_test_dir("deser");
        let run = MjolnirRun::from_dir(&dir);

        // Before files exist
        assert!(run.metadata().is_err());
        assert!(run.vulnerabilities().is_err());

        // Write metadata.json
        let meta_json = r#"{
            "repo": "https://github.com/google/caliptra-sw.git",
            "model": "gemini-2.5-pro",
            "ref": "main",
            "target_commit": "abc1234",
            "timestamp": "2026-08-20T10:00:00Z",
            "mode": "autonomous",
            "job": "ci-audit",
            "schema_version": "v1"
        }"#;
        fs::write(dir.join(Mjolnir::METADATA_JSON), meta_json).unwrap();

        let meta = run.metadata().expect("Failed to deserialize metadata");
        assert_eq!(
            meta.repo.as_deref(),
            Some("https://github.com/google/caliptra-sw.git")
        );
        assert_eq!(meta.model.as_deref(), Some("gemini-2.5-pro"));
        assert_eq!(meta.target_commit.as_deref(), Some("abc1234"));
        assert_eq!(meta.timestamp.as_deref(), Some("2026-08-20T10:00:00Z"));
        assert_eq!(meta.mode.as_deref(), Some("autonomous"));

        let idents = run.resolve_run_identifiers();
        assert_eq!(idents.project, "caliptra-sw");
        assert_eq!(idents.job, "");
        assert_eq!(idents.run_id, "2026-08-20T10:00:00Z");

        // Write vulnerabilities.json
        let vulns_json = r#"[
            {
                "title": "Buffer Overflow in Crypto Driver",
                "severity": "HIGH",
                "file": "src/crypto/driver.rs",
                "location": "src/crypto/driver.rs:42",
                "description": "Unbounded copy",
                "recommendation": "Use bounded slice copy"
            }
        ]"#;
        fs::write(dir.join(Mjolnir::VULNERABILITIES_JSON), vulns_json).unwrap();

        let vulns = run
            .vulnerabilities()
            .expect("Failed to deserialize vulnerabilities");
        assert_eq!(vulns.len(), 1);
        assert_eq!(
            vulns[0].title.as_deref(),
            Some("Buffer Overflow in Crypto Driver")
        );
        assert_eq!(vulns[0].severity.as_deref(), Some("HIGH"));
        assert_eq!(
            vulns.findings()[0].file.as_deref(),
            Some("src/crypto/driver.rs")
        );

        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_vulnerabilities_minimal_fallback() {
        let dir = create_test_dir("minimal");
        let run = MjolnirRun::from_dir(&dir);

        let minimal_json = r#"[
            {
                "title": "Low severity finding",
                "severity": "LOW",
                "file": "main.rs",
                "location": "main.rs:1",
                "description": "Minor issue",
                "recommendation": "Fix it"
            }
        ]"#;
        fs::write(
            dir.join(Mjolnir::VULNERABILITIES_MINIMAL_JSON),
            minimal_json,
        )
        .unwrap();

        let vulns = run
            .vulnerabilities()
            .expect("Failed to deserialize minimal vulns");
        assert_eq!(vulns.len(), 1);
        assert_eq!(vulns[0].title.as_deref(), Some("Low severity finding"));
        assert!(vulns.raw_json().contains("Low severity finding"));

        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_discover_and_find_latest_run() {
        let root = create_test_dir("discovery");
        let run1 = root.join("run1");
        let run2 = root.join("nested/run2");
        fs::create_dir_all(&run1).unwrap();
        fs::create_dir_all(&run2).unwrap();

        fs::write(run1.join(Mjolnir::VULNERABILITIES_JSON), "[]").unwrap();
        fs::write(run2.join(Mjolnir::VULNERABILITIES_MINIMAL_JSON), "[]").unwrap();

        let workspace = Mjolnir::new(&root);
        let runs = workspace.runs();
        assert_eq!(runs.len(), 2);

        let latest = workspace.latest_run().expect("Failed to find latest run");
        assert!(latest.dir == run1 || latest.dir == run2);

        // Directly querying run1
        let direct = Mjolnir::new(&run1)
            .latest_run()
            .expect("Failed direct find");
        assert_eq!(direct.dir, run1);

        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn test_discover_structured_runs() {
        let root = create_test_dir("structured");
        let run_dir = root.join("my-project/my-job/run-001");
        fs::create_dir_all(&run_dir).unwrap();
        fs::write(
            run_dir.join(Mjolnir::METADATA_JSON),
            r#"{"schema_version":"v1"}"#,
        )
        .unwrap();
        fs::write(run_dir.join(Mjolnir::VULNERABILITIES_JSON), "[]").unwrap();

        let workspace = Mjolnir::new(&root);
        let structured = workspace.structured_runs();
        assert_eq!(structured.len(), 1);
        assert_eq!(structured[0].identifiers.project, "my-project");
        assert_eq!(structured[0].identifiers.job, "my-job");
        assert_eq!(structured[0].identifiers.run_id, "run-001");

        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn test_default_discovery() {
        let mjolnir = Mjolnir::default();
        assert!(mjolnir.root.exists());
        // Should discover either the workspace root containing Cargo.toml/web/xtask or fallback to valid cwd
        assert!(mjolnir.root.is_dir());
    }
}
