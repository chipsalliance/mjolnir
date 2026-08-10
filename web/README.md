<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Mjolnir WebAssembly Dashboard

This directory contains the high-performance WebAssembly (WASM) and Rust dashboard for Mjolnir security findings and telemetry flow visualization.

## Architecture

- **WebAssembly Engine (`web/src/lib.rs`)**: Compiled from Rust to WASM using `wasm-bindgen`. Executes fast client-side sorting, vulnerability filtering, multi-phase Sankey flow calculations, and summary statistics.
- **Web Worker Offloading (`web/wasm-worker.js`)**: Spawns a background browser thread to execute all WASM filtering and Sankey graph transformations without blocking UI event loops or DOM rendering.
- **Dashboard Frontend (`web/app.js`, `web/index.html`, `web/style.css`)**: Modern single-page application (SPA) rendering findings tables, file tree views, token telemetry metrics, and Google Charts Sankey flow diagrams.
- **Local Development Server & Deployment CLI (`xtask/src/main.rs`)**: Rust `cargo xtask` runner that compiles WASM modules, serves local static files + REST API endpoints (`/api/runs`, `/api/usage`, `/api/run/...`), and syncs web dashboard assets to Google Cloud Storage (GCS).

## Building & Running

### 1. Launch Local Web Viewer Server

To build the WASM module and start the local development server (default: `http://localhost:8080`):

```bash
nix run .#web-viewer
```

Or using `cargo xtask`:

```bash
nix-shell -p cargo rustc wasm-bindgen-cli lld --run "cargo xtask web --serve"
```

### 2. Build WebAssembly Module Only

```bash
nix-shell -p cargo rustc wasm-bindgen-cli lld --run "cargo xtask web"
```

### 3. Deploy Web Dashboard to GCS

```bash
nix run .#deploy-gcs-web
```

### 4. Sync Scan Runs to GCS

```bash
nix run .#deploy-gcs-runs
```

By default, test project runs (e.g. `tests` or `test_*`) are excluded. To include test runs or token usage telemetry:

```bash
nix run .#deploy-gcs-runs -- --include-tests --include-usage
```
