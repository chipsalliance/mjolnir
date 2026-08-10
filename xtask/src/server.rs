// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

use std::fs;
use std::io::Read;
use std::path::Path;
use tiny_http::{Header, Response, Server};

use crate::scanner::scan_v1_runs;
use crate::telemetry::{get_all_usage, get_run_detail};

/// Serves Mjolnir static web assets and REST API endpoints over HTTP
pub fn serve_local(web_dir: &Path, runs_dir: &Path, port: u16) {
    let addr = format!("[::]:{}", port);
    let server = Server::http(&addr).expect("Failed to start HTTP server");

    println!(
        "\nMjolnir Rust Local Viewer Server running at http://localhost:{}",
        port
    );
    println!("Serving local runs from: {}\n", runs_dir.display());

    for request in server.incoming_requests() {
        let raw_url = request.url();
        let clean_url = raw_url.split('?').next().unwrap_or(raw_url);
        let path = if clean_url.starts_with("http://") || clean_url.starts_with("https://") {
            let parts: Vec<&str> = clean_url.splitn(4, '/').collect();
            if parts.len() > 3 {
                format!("/{}", parts[3])
            } else {
                "/".to_string()
            }
        } else {
            clean_url.to_string()
        };

        if path == "/api/runs" {
            let json_resp = scan_v1_runs(runs_dir);
            let response = Response::from_string(json_resp)
                .with_header(
                    Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap(),
                )
                .with_header(
                    Header::from_bytes(&b"Access-Control-Allow-Origin"[..], &b"*"[..]).unwrap(),
                )
                .with_header(Header::from_bytes(&b"Cache-Control"[..], &b"no-cache"[..]).unwrap());
            let _ = request.respond(response);
            continue;
        }

        if path == "/api/usage" {
            let json_resp = get_all_usage(runs_dir);
            let response = Response::from_string(json_resp)
                .with_header(
                    Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap(),
                )
                .with_header(
                    Header::from_bytes(&b"Access-Control-Allow-Origin"[..], &b"*"[..]).unwrap(),
                )
                .with_header(Header::from_bytes(&b"Cache-Control"[..], &b"no-cache"[..]).unwrap());
            let _ = request.respond(response);
            continue;
        }

        if path.starts_with("/api/run/") {
            let parts: Vec<&str> = path.trim_start_matches("/api/run/").split('/').collect();
            if parts.len() >= 3 {
                let (proj, job, run_id) = (parts[0], parts[1], parts[2]);
                let run_folder = runs_dir.join(proj).join(job).join(run_id);
                let json_resp = get_run_detail(&run_folder);
                let response = Response::from_string(json_resp)
                    .with_header(
                        Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap(),
                    )
                    .with_header(
                        Header::from_bytes(&b"Access-Control-Allow-Origin"[..], &b"*"[..]).unwrap(),
                    )
                    .with_header(
                        Header::from_bytes(&b"Cache-Control"[..], &b"no-cache"[..]).unwrap(),
                    );
                let _ = request.respond(response);
                continue;
            }
        }

        // Static File Serving
        let rel_path = if path == "/" || path.is_empty() {
            "index.html"
        } else {
            path.trim_start_matches('/')
        };
        let mut file_path = web_dir.join(rel_path);
        if !file_path.is_file() && rel_path.starts_with("web/") {
            file_path = web_dir.join(rel_path.strip_prefix("web/").unwrap_or(rel_path));
        }

        if file_path.is_file() {
            let content_type = match file_path.extension().and_then(|s| s.to_str()) {
                Some("html") => "text/html; charset=utf-8",
                Some("js") => "application/javascript",
                Some("wasm") => "application/wasm",
                Some("css") => "text/css",
                Some("json") => "application/json",
                _ => "application/octet-stream",
            };

            if let Ok(mut f) = fs::File::open(&file_path) {
                let mut buffer = Vec::new();
                if f.read_to_end(&mut buffer).is_ok() {
                    let response = Response::from_data(buffer)
                        .with_header(
                            Header::from_bytes(&b"Content-Type"[..], content_type.as_bytes())
                                .unwrap(),
                        )
                        .with_header(
                            Header::from_bytes(&b"Access-Control-Allow-Origin"[..], &b"*"[..])
                                .unwrap(),
                        )
                        .with_header(
                            Header::from_bytes(&b"Cache-Control"[..], &b"no-cache"[..]).unwrap(),
                        );
                    let _ = request.respond(response);
                    continue;
                }
            }
        }

        let _ = request.respond(Response::from_string("404 Not Found").with_status_code(404));
    }
}
