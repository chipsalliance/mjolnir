// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

use std::fs;
use std::path::Path;
use std::process::Command;

/// Compiles the Rust WebAssembly module and generates JS bindings via wasm-bindgen
pub fn build_wasm(root_dir: &Path, include_token_usage: bool, include_tool_usage: bool) {
    let web_dir = root_dir.join("web");
    println!(
        "Building WebAssembly dashboard in {} (Token Usage: {}, Tool Usage: {})...",
        web_dir.display(),
        include_token_usage,
        include_tool_usage
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

    // Build-time conditional token usage module generation
    let dist_token_usage_file = dist_dir.join("token_usage_module.js");
    if include_token_usage {
        let src_token_usage_file = web_dir.join("src/token_usage_module.js");
        if src_token_usage_file.exists() {
            fs::copy(src_token_usage_file, &dist_token_usage_file)
                .expect("Failed to copy token_usage_module.js into dist/");
        }
    } else {
        let stub_content = "// Licensed under the Apache-2.0 license\n// SPDX-License-Identifier: Apache-2.0\nexport function registerTokenUsageModule() {}\nexport function renderProjectTokenUsage() { return \"\"; }\nexport function renderRunTokenUsage() { return \"\"; }\n";
        fs::write(dist_token_usage_file, stub_content)
            .expect("Failed to write stub token_usage_module.js");
    }

    // Build-time conditional tool usage module generation
    let dist_tool_usage_file = dist_dir.join("tool_usage_module.js");
    if include_tool_usage {
        let src_tool_usage_file = web_dir.join("src/tool_usage_module.js");
        if src_tool_usage_file.exists() {
            fs::copy(src_tool_usage_file, &dist_tool_usage_file)
                .expect("Failed to copy tool_usage_module.js into dist/");
        }
    } else {
        let stub_content = "// Licensed under the Apache-2.0 license\n// SPDX-License-Identifier: Apache-2.0\nexport function registerToolUsageModule() {}\nexport function renderProjectToolUsage() { return \"\"; }\nexport function renderRunToolUsage() { return \"\"; }\n";
        fs::write(dist_tool_usage_file, stub_content)
            .expect("Failed to write stub tool_usage_module.js");
    }

    // Generate build metadata with UTC timestamp
    let build_info_file = dist_dir.join("build_info.js");
    let timestamp = match Command::new("date")
        .args(["-u", "+%Y-%m-%dT%H:%M:%SZ"])
        .output()
    {
        Ok(out) if out.status.success() => String::from_utf8_lossy(&out.stdout).trim().to_string(),
        _ => "Unknown".to_string(),
    };
    let build_info_content = format!(
        "// Licensed under the Apache-2.0 license\n// SPDX-License-Identifier: Apache-2.0\nexport const BUILD_TIMESTAMP = \"{}\";\n",
        timestamp
    );
    let _ = fs::write(build_info_file, build_info_content);

    println!("WebAssembly module built successfully in dist/");
}
