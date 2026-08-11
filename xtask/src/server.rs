// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

use std::fs;
use std::io::Read;
use std::path::Path;
use tiny_http::{Header, Response, Server};

/// Serves Mjolnir static web assets and local run outputs over HTTP
pub fn serve_local(web_dir: &Path, runs_dir: &Path, port: u16) {
    let addr = format!("[::]:{}", port);
    let server = Server::http(&addr).expect("Failed to start HTTP server");

    println!(
        "\nMjolnir Local Viewer Server running at http://localhost:{}",
        port
    );
    println!("Serving local runs from: {}\n", runs_dir.display());

    for request in server.incoming_requests() {
        let raw_url = request.url();

        // GCS XML bucket listing simulation for ?prefix=v1/runs/
        if raw_url.contains("prefix=v1/runs") {
            let mut keys = Vec::new();
            if runs_dir.exists() {
                for proj_entry in fs::read_dir(runs_dir).into_iter().flatten().flatten() {
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
                            let meta_file = run_path.join("metadata.json");
                            if meta_file.exists() {
                                keys.push(format!(
                                    "v1/runs/{}/{}/{}/metadata.json",
                                    proj_name, job_name, run_id
                                ));
                            }
                        }
                    }
                }
            }

            let contents_xml: String = keys
                .into_iter()
                .map(|k| format!("<Contents><Key>{}</Key></Contents>", k))
                .collect();

            let xml_resp = format!(
                r#"<?xml version="1.0" encoding="UTF-8"?><ListBucketResult xmlns="http://doc.s3.amazonaws.com/2006-03-01"><Name>mjolnir-local</Name><Prefix>v1/runs/</Prefix>{}</ListBucketResult>"#,
                contents_xml
            );

            let response = Response::from_string(xml_resp)
                .with_header(
                    Header::from_bytes(&b"Content-Type"[..], &b"text/xml; charset=utf-8"[..])
                        .unwrap(),
                )
                .with_header(
                    Header::from_bytes(&b"Access-Control-Allow-Origin"[..], &b"*"[..]).unwrap(),
                )
                .with_header(Header::from_bytes(&b"Cache-Control"[..], &b"no-cache"[..]).unwrap());
            let _ = request.respond(response);
            continue;
        }

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

        // Static File Serving
        let rel_path = if path == "/" || path.is_empty() {
            "index.html"
        } else {
            path.trim_start_matches('/')
        };

        let mut file_path = if rel_path.starts_with("v1/runs/") {
            let sub = rel_path.strip_prefix("v1/runs/").unwrap_or(rel_path);
            runs_dir.join(sub)
        } else {
            web_dir.join(rel_path)
        };

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
