// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

mod build;
mod deploy;
mod scanner;
mod server;
mod telemetry;

use std::env;
use std::path::{Path, PathBuf};

fn main() {
    let args: Vec<String> = env::args().collect();
    let task = args.get(1).map(|s| s.as_str()).unwrap_or("help");

    let root = root_dir();

    match task {
        "web" => {
            let serve = args.iter().any(|a| a == "--serve");
            let include_usage = args.iter().any(|a| a == "--include-usage");
            let port = args
                .iter()
                .position(|a| a == "--port")
                .and_then(|i| args.get(i + 1))
                .and_then(|p| p.parse::<u16>().ok())
                .unwrap_or(8080);

            build::build_wasm(&root, include_usage);

            if serve {
                let web_dir = root.join("web");
                let runs_dir = root.join("output/v1/runs");
                server::serve_local(&web_dir, &runs_dir, port);
            }
        }
        "deploy-gcs-web" => {
            let include_usage = args.iter().any(|a| a == "--include-usage");
            build::build_wasm(&root, include_usage);
            deploy::deploy_gcs(&root, &["--web"]);
        }
        "deploy-gcs-runs" => {
            let include_usage = args.iter().any(|a| a == "--include-usage");
            let include_tests = args.iter().any(|a| a == "--include-tests");
            let mut flags = vec!["--runs"];
            if include_usage {
                flags.push("--include-usage");
            }
            if include_tests {
                flags.push("--include-tests");
            }
            deploy::deploy_gcs(&root, &flags);
        }
        _ => print_help(),
    }
}

fn print_help() {
    println!("Mjolnir Development Task Runner (xtask)\n");
    println!("USAGE:");
    println!("    cargo xtask web [--serve] [--port <PORT>]");
    println!("    cargo xtask deploy-gcs-web");
    println!("    cargo xtask deploy-gcs-runs\n");
    println!("COMMANDS:");
    println!("    web              Builds the WebAssembly dashboard module");
    println!("    web --serve      Builds and starts a local HTTP viewer server (default: http://localhost:8080)");
    println!("    deploy-gcs-web   Builds WASM & deploys static web dashboard to GCS bucket defined in .env");
    println!(
        "    deploy-gcs-runs  Syncs local output/v1/runs/ to GCS bucket (skipping existing runs)"
    );
}

fn root_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .to_path_buf()
}
