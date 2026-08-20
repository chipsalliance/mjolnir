// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

use crate::files::Mjolnir;
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
            let structured_runs = Mjolnir::new(runs_dir).structured_runs();
            let keys: Vec<String> = structured_runs
                .into_iter()
                .filter_map(|sr| {
                    if sr.run.metadata().is_ok() {
                        Some(format!(
                            "v1/runs/{}/{}/{}/{}",
                            sr.identifiers.project,
                            sr.identifiers.job,
                            sr.identifiers.run_id,
                            Mjolnir::METADATA_JSON
                        ))
                    } else {
                        None
                    }
                })
                .collect();

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

        if let Some((buffer, content_type)) = read_static_asset(&file_path) {
            let response = Response::from_data(buffer)
                .with_header(
                    Header::from_bytes(&b"Content-Type"[..], content_type.as_bytes()).unwrap(),
                )
                .with_header(
                    Header::from_bytes(&b"Access-Control-Allow-Origin"[..], &b"*"[..]).unwrap(),
                )
                .with_header(Header::from_bytes(&b"Cache-Control"[..], &b"no-cache"[..]).unwrap());
            let _ = request.respond(response);
            continue;
        }

        let _ = request.respond(Response::from_string("404 Not Found").with_status_code(404));
    }
}

fn read_static_asset(path: &Path) -> Option<(Vec<u8>, &'static str)> {
    if !path.is_file() {
        return None;
    }
    let content_type = match path.extension().and_then(|s| s.to_str()) {
        Some("html") => "text/html; charset=utf-8",
        Some("js") => "application/javascript",
        Some("wasm") => "application/wasm",
        Some("css") => "text/css",
        Some("json") => "application/json",
        _ => "application/octet-stream",
    };
    let buffer = std::fs::read(path).ok()?;
    Some((buffer, content_type))
}
