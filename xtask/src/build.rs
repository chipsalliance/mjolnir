// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

use std::fs;
use std::path::Path;
use std::process::Command;

/// Compiles the Rust WebAssembly module and generates JS bindings via wasm-bindgen
pub fn build_wasm(root_dir: &Path, include_usage: bool) {
    let web_dir = root_dir.join("web");
    println!(
        "Building WebAssembly dashboard in {} (Include usage telemetry: {})...",
        web_dir.display(),
        include_usage
    );

    let status = Command::new("cargo")
        .args([
            "build",
            "--package",
            "mjolnir-dashboard-wasm",
            "--target",
            "wasm32-unknown-unknown",
            "--release",
        ])
        .current_dir(root_dir)
        .status()
        .expect("Failed to execute cargo build");

    if !status.success() {
        eprintln!("Cargo WASM compilation failed.");
        std::process::exit(1);
    }

    let wasm_file = if root_dir
        .join("target/wasm32-unknown-unknown/release/mjolnir_dashboard_wasm.wasm")
        .exists()
    {
        root_dir.join("target/wasm32-unknown-unknown/release/mjolnir_dashboard_wasm.wasm")
    } else {
        web_dir.join("target/wasm32-unknown-unknown/release/mjolnir_dashboard_wasm.wasm")
    };

    let dist_dir = web_dir.join("dist");

    let status = Command::new("wasm-bindgen")
        .args([
            wasm_file.to_str().unwrap(),
            "--out-dir",
            dist_dir.to_str().unwrap(),
            "--target",
            "web",
        ])
        .current_dir(&web_dir)
        .status()
        .expect("Failed to execute wasm-bindgen");

    if !status.success() {
        eprintln!("wasm-bindgen failed.");
        std::process::exit(1);
    }

    // Build-time conditional usage module generation
    let dist_usage_file = dist_dir.join("usage_module.js");
    if include_usage {
        let src_usage_file = web_dir.join("src/usage_module.js");
        if src_usage_file.exists() {
            fs::copy(src_usage_file, dist_usage_file)
                .expect("Failed to copy usage_module.js into dist/");
        }
    } else {
        let stub_content = "// Licensed under the Apache-2.0 license\n// SPDX-License-Identifier: Apache-2.0\nexport function registerUsageModule() {}\n";
        fs::write(dist_usage_file, stub_content).expect("Failed to write stub usage_module.js");
    }

    println!("WebAssembly module built successfully in dist/");
}
