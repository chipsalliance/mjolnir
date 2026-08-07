// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

import initWasm, {
  compute_summary,
  filter_vulnerabilities,
  compute_sankey_flow,
  compute_project_sankey_flow,
  compute_run_sankey_flow
} from './dist/mjolnir_dashboard_wasm.js';

let isReady = false;

async function init() {
  try {
    await initWasm({ module_or_path: './dist/mjolnir_dashboard_wasm_bg.wasm' });
    isReady = true;
    self.postMessage({ type: 'ready' });
  } catch (err) {
    self.postMessage({ type: 'error', error: err ? (err.message || String(err)) : 'Failed to initialize WASM in Web Worker' });
  }
}

self.onmessage = async (e) => {
  const { id, type, payload } = e.data;

  if (type === 'init') {
    await init();
    return;
  }

  if (!isReady) {
    self.postMessage({ id, type, error: 'WASM worker module not ready' });
    return;
  }

  try {
    let result;
    if (type === 'filter_vulnerabilities') {
      const { vulnerabilitiesJson, query, severityFilter, statusFilter, sortOrder } = payload;
      result = filter_vulnerabilities(vulnerabilitiesJson, query, severityFilter, statusFilter, sortOrder);
    } else if (type === 'compute_sankey_flow') {
      const { runsJson, hideTests } = payload;
      result = compute_sankey_flow(runsJson, hideTests);
    } else if (type === 'compute_project_sankey_flow') {
      const { runsJson, targetProject } = payload;
      result = compute_project_sankey_flow(runsJson, targetProject);
    } else if (type === 'compute_run_sankey_flow') {
      const { vulnerabilitiesJson } = payload;
      result = compute_run_sankey_flow(vulnerabilitiesJson);
    } else if (type === 'compute_summary') {
      const { vulnerabilitiesJson } = payload;
      result = compute_summary(vulnerabilitiesJson);
    } else {
      throw new Error(`Unknown worker message type: ${type}`);
    }

    self.postMessage({ id, type, result });
  } catch (err) {
    self.postMessage({ id, type, error: err ? (err.message || String(err)) : 'Worker task execution error' });
  }
};
