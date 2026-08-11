// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

mod build;
mod deploy;
mod server;

use std::env;
use std::path::{Path, PathBuf};

fn main() {
    let args: Vec<String> = env::args().collect();
    let task = args.get(1).map(|s| s.as_str()).unwrap_or("help");

    let root = root_dir();

    match task {
        "web" => {
            let mut serve = false;
            let mut include_token_usage = false;
            let mut include_tool_usage = false;
            let mut port = 8080u16;

            let mut i = 2;
            while i < args.len() {
                let arg = &args[i];
                match arg.as_str() {
                    "--serve" => serve = true,
                    "--include-token-usage" => include_token_usage = true,
                    "--include-tool-usage" => include_tool_usage = true,
                    "--port" => {
                        i += 1;
                        if i >= args.len() {
                            eprintln!("Error: --port requires a port number argument.");
                            std::process::exit(1);
                        }
                        port = args[i].parse::<u16>().unwrap_or_else(|_| {
                            eprintln!("Error: Invalid port number '{}'.", args[i]);
                            std::process::exit(1);
                        });
                    }
                    _ => {
                        eprintln!(
                            "Error: Unrecognized argument '{}' for task 'web'.\nAllowed flags: --serve, --port <PORT>, --include-token-usage, --include-tool-usage",
                            arg
                        );
                        std::process::exit(1);
                    }
                }
                i += 1;
            }

            build::build_wasm(&root, include_token_usage, include_tool_usage);

            if serve {
                let web_dir = root.join("web");
                let runs_dir = root.join("output/v1/runs");
                server::serve_local(&web_dir, &runs_dir, port);
            }
        }
        "deploy-gcs-web" => {
            let mut include_token_usage = false;
            let mut include_tool_usage = false;

            for arg in &args[2..] {
                match arg.as_str() {
                    "--include-token-usage" => include_token_usage = true,
                    "--include-tool-usage" => include_tool_usage = true,
                    _ => {
                        eprintln!(
                            "Error: Unrecognized argument '{}' for task 'deploy-gcs-web'.\nAllowed flags: --include-token-usage, --include-tool-usage",
                            arg
                        );
                        std::process::exit(1);
                    }
                }
            }

            build::build_wasm(&root, include_token_usage, include_tool_usage);
            deploy::deploy_gcs(&root, &["--web"]);
        }
        "deploy-gcs-runs" => {
            let mut include_tests = false;

            for arg in &args[2..] {
                match arg.as_str() {
                    "--include-tests" => include_tests = true,
                    _ => {
                        eprintln!(
                            "Error: Unrecognized argument '{}' for task 'deploy-gcs-runs'.\nAllowed flags: --include-tests",
                            arg
                        );
                        std::process::exit(1);
                    }
                }
            }

            let mut flags = vec!["--runs"];
            if include_tests {
                flags.push("--include-tests");
            }
            deploy::deploy_gcs(&root, &flags);
        }
        "help" | "-h" | "--help" => print_help(),
        _ => {
            eprintln!("Error: Unrecognized task '{}'.\n", task);
            print_help();
            std::process::exit(1);
        }
    }
}

fn print_help() {
    println!("Mjolnir Development Task Runner (xtask)\n");
    println!("USAGE:");
    println!("    cargo xtask web [--serve] [--port <PORT>] [--include-token-usage] [--include-tool-usage]");
    println!("    cargo xtask deploy-gcs-web [--include-token-usage] [--include-tool-usage]");
    println!("    cargo xtask deploy-gcs-runs [--include-tests]\n");
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
