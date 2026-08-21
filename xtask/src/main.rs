// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

mod build;
mod deploy;
mod files;
mod report;
mod server;

use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "xtask", about = "Mjolnir Development Task Runner (xtask)")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Builds the WebAssembly dashboard module
    Web {
        /// Starts a local HTTP viewer server
        #[arg(long)]
        serve: bool,

        /// Port to serve local viewer
        #[arg(long, default_value_t = 8080)]
        port: u16,

        /// Include token usage metrics module
        #[arg(long)]
        include_token_usage: bool,

        /// Include tool usage metrics module
        #[arg(long)]
        include_tool_usage: bool,
    },
    /// Builds WASM & deploys static web dashboard to target GCS bucket
    DeployGcsWeb {
        /// Target GCS bucket name
        #[arg(short, long)]
        bucket: String,

        /// Include token usage metrics module
        #[arg(long)]
        include_token_usage: bool,

        /// Include tool usage metrics module
        #[arg(long)]
        include_tool_usage: bool,
    },
    /// Syncs local output/v1/runs/ to target GCS bucket
    DeployGcsRuns {
        /// Target GCS bucket name
        #[arg(long)]
        bucket: String,

        /// Output directory containing runs
        #[arg(long)]
        output_dir: String,

        /// Include test runs
        #[arg(long)]
        include_tests: bool,
    },
    /// Generates a report from audit run findings
    EmitReport {
        /// Output file path (e.g. report.md)
        #[arg(short, long)]
        output: PathBuf,

        /// Report format
        #[arg(short, long, default_value = "markdown")]
        format: String,
    },
}

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    let root = root_dir();

    match cli.command {
        Command::Web {
            serve,
            port,
            include_token_usage,
            include_tool_usage,
        } => {
            build::build_wasm(&root, include_token_usage, include_tool_usage);

            if serve {
                let web_dir = root.join("web");
                let runs_dir = root.join("output/v1/runs");
                server::serve_local(&web_dir, &runs_dir, port);
            }
        }
        Command::DeployGcsWeb {
            bucket,
            include_token_usage,
            include_tool_usage,
        } => {
            build::build_wasm(&root, include_token_usage, include_tool_usage);

            let bucket_flag = format!("--bucket={}", bucket);
            let flags = [&bucket_flag[..]];
            deploy::deploy_gcs_web(&root, &flags);
        }
        Command::DeployGcsRuns {
            bucket,
            output_dir,
            include_tests,
        } => {
            let mut flags = vec![
                format!("--bucket={}", bucket),
                format!("--output-dir={}", output_dir),
            ];
            if include_tests {
                flags.push("--include-tests".to_string());
            }
            let flag_refs: Vec<&str> = flags.iter().map(|s| s.as_str()).collect();
            deploy::deploy_gcs_runs(&root, &flag_refs);
        }
        Command::EmitReport { output, format } => {
            report::emit_report(&output, &format)?;
        }
    }

    Ok(())
}

fn root_dir() -> PathBuf {
    files::Mjolnir::default().root
}
