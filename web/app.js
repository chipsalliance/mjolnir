// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

import init, {
  compute_summary,
  filter_vulnerabilities,
  compute_sankey_flow,
  compute_project_sankey_flow,
  compute_run_sankey_flow
} from './dist/mjolnir_dashboard_wasm.js';
import { registerTokenUsageModule } from './dist/token_usage_module.js';
import { registerToolUsageModule } from './dist/tool_usage_module.js';
import { BUILD_TIMESTAMP } from './dist/build_info.js';


export function getApiEndpoint(endpoint) {
  let base = window.location.pathname;
  if (!base.endsWith("/") && !base.endsWith(".html")) {
    base += "/";
  }
  const cleanEndpoint = endpoint.replace(/^\//, "");
  return new URL(cleanEndpoint, window.location.origin + base).href;
}

let dynamicRoutes = {};

let runsState = [];
let currentRunVulns = [];
let currentRouteParams = {};
let hideTests = localStorage.getItem("mjolnir_hide_tests") === "true";

let worker = null;
let workerReady = false;
let workerTaskId = 0;
const workerCallbacks = new Map();

function initWasmWorker() {
  try {
    worker = new Worker('web/wasm-worker.js', { type: 'module' });

    worker.onmessage = (e) => {
      const { id, type, result, error } = e.data;

      if (type === 'ready') {
        workerReady = true;
        console.log("WASM Web Worker initialized and ready.");
        return;
      }

      if (type === 'error' && !id) {
        console.warn("WASM Web Worker error, falling back to main thread:", error);
        return;
      }

      if (id && workerCallbacks.has(id)) {
        const { resolve, reject } = workerCallbacks.get(id);
        workerCallbacks.delete(id);
        if (error) {
          reject(new Error(error));
        } else {
          resolve(result);
        }
      }
    };

    worker.postMessage({ type: 'init' });
  } catch (err) {
    console.warn("Web Worker creation failed, using main thread fallback:", err);
  }
}

let mainWasmPromise = null;

function ensureMainThreadWasm() {
  if (!mainWasmPromise) {
    mainWasmPromise = init({ module_or_path: './dist/mjolnir_dashboard_wasm_bg.wasm' }).catch(err => {
      console.warn("Main thread WebAssembly init warning:", err);
    });
  }
  return mainWasmPromise;
}

async function runWorkerTask(type, payload) {
  if (!worker || !workerReady) {
    return await executeMainThreadWasm(type, payload);
  }

  return new Promise((resolve, reject) => {
    const id = ++workerTaskId;
    workerCallbacks.set(id, { resolve, reject });
    worker.postMessage({ id, type, payload });
  });
}

async function executeMainThreadWasm(type, payload) {
  await ensureMainThreadWasm();

  if (type === 'filter_vulnerabilities') {
    const { vulnerabilitiesJson, query, severityFilter, statusFilter, sortOrder } = payload;
    return filter_vulnerabilities(vulnerabilitiesJson, query, severityFilter, statusFilter, sortOrder);
  } else if (type === 'compute_sankey_flow') {
    const { runsJson, hideTests } = payload;
    return compute_sankey_flow(runsJson, hideTests);
  } else if (type === 'compute_project_sankey_flow') {
    const { runsJson, targetProject } = payload;
    return compute_project_sankey_flow(runsJson, targetProject);
  } else if (type === 'compute_run_sankey_flow') {
    const { vulnerabilitiesJson } = payload;
    return compute_run_sankey_flow(vulnerabilitiesJson);
  } else if (type === 'compute_summary') {
    const { vulnerabilitiesJson } = payload;
    return compute_summary(vulnerabilitiesJson);
  }
  throw new Error(`Unknown main thread task type: ${type}`);
}

async function apiFilterVulnerabilities(vulnerabilitiesJson, query, severityFilter, statusFilter, sortOrder) {
  return runWorkerTask('filter_vulnerabilities', { vulnerabilitiesJson, query, severityFilter, statusFilter, sortOrder });
}

async function apiComputeSankeyFlow(runsJson, hideTests) {
  return runWorkerTask('compute_sankey_flow', { runsJson, hideTests });
}

async function apiComputeProjectSankeyFlow(runsJson, targetProject) {
  return runWorkerTask('compute_project_sankey_flow', { runsJson, targetProject });
}

async function apiComputeRunSankeyFlow(vulnerabilitiesJson) {
  return runWorkerTask('compute_run_sankey_flow', { vulnerabilitiesJson });
}

async function apiComputeSummary(vulnerabilitiesJson) {
  return runWorkerTask('compute_summary', { vulnerabilitiesJson });
}

async function bootstrap() {
  setupEventListeners();
  const navContainer = document.querySelector(".sidebar-nav");
  registerTokenUsageModule(navContainer, dynamicRoutes, renderEmptyState);
  registerToolUsageModule(navContainer, dynamicRoutes, renderEmptyState);

  // Initialize Web Worker and WASM background fallbacks
  try {
    initWasmWorker();
  } catch (e) {
    console.warn("WASM Web Worker init warning:", e);
  }

  // Pre-load main thread fallback WASM
  ensureMainThreadWasm();

  // Load Google Charts for Sankey flow
  try {
    if (window.google && window.google.charts) {
      window.google.charts.load('current', { 'packages': ['sankey'] });
    }
  } catch (e) {
    console.warn("Google Charts load warning:", e);
  }

  await fetchRunsData();
  handleRoute();
}

function setupEventListeners() {
  window.addEventListener("hashchange", handleRoute);

  // Keyboard shortcut '/' to focus search input, 'Esc' to close modal
  window.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "SELECT") {
      const searchInput = document.getElementById("search-input");
      if (searchInput) {
        e.preventDefault();
        searchInput.focus();
      }
    } else if (e.key === "Escape") {
      closeFindingModal();
    }
  });


  document.getElementById("modal-close").addEventListener("click", closeFindingModal);
}

function closeFindingModal() {
  document.getElementById("vulnerability-modal").classList.add("hidden");
  if (currentRouteParams.proj && currentRouteParams.job && currentRouteParams.runId) {
    // Restore run hash without finding suffix
    const runHash = `#/run/${currentRouteParams.proj}/${currentRouteParams.job}/${currentRouteParams.runId}`;
    if (window.location.hash !== runHash) {
      history.replaceState(null, "", runHash);
    }
  }
}

async function fetchRunsData() {
  try {
    const res = await fetch(getApiEndpoint("api/runs"));
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    runsState = await res.json();
  } catch (err) {
    console.warn("Could not fetch runs data:", err);
    runsState = [];
  }
  updateFooterTimestamp();
  renderSidebarNavigation();
}

function updateFooterTimestamp() {
  const el = document.getElementById("footer-last-updated");
  if (!el) return;

  if (typeof BUILD_TIMESTAMP !== "undefined" && BUILD_TIMESTAMP && BUILD_TIMESTAMP !== "Unknown") {
    const t = new Date(BUILD_TIMESTAMP);
    if (!isNaN(t.getTime())) {
      el.textContent = t.toLocaleString();
      return;
    }
    el.textContent = BUILD_TIMESTAMP;
    return;
  }
  el.textContent = "N/A";
}

function renderSidebarNavigation() {
  const projContainer = document.getElementById("project-nav-list");
  const runsContainer = document.getElementById("recent-runs-nav-list");

  if (!runsState || runsState.length === 0) {
    if (projContainer) projContainer.innerHTML = `<div class="nav-subitem">No Projects Yet</div>`;
    if (runsContainer) runsContainer.innerHTML = `<div class="nav-subitem">No Runs Yet</div>`;
    return;
  }

  // Projects Nav
  const projectsMap = {};
  runsState.forEach(r => {
    const p = r.project || "default";
    if (!projectsMap[p]) projectsMap[p] = [];
    projectsMap[p].push(r);
  });

  let projHtml = "";
  Object.keys(projectsMap).sort().forEach(pName => {
    const count = projectsMap[pName].length;
    projHtml += `
      <a href="#/project/${pName}" class="nav-item" id="nav-proj-${pName}">
        <span>${pName}</span>
        <span class="badge" style="margin-left: auto; background-color: var(--bg-card);">${count}</span>
      </a>`;
  });
  if (projContainer) projContainer.innerHTML = projHtml;

  // Recent 10 Runs Nav
  const recent10 = runsState.slice(0, 10);
  let runsHtml = "";
  recent10.forEach(r => {
    const shortId = r.run_id.length > 18 ? r.run_id.substring(0, 18) : r.run_id;
    const count = r.vuln_count ?? 0;
    const badgeClass = count === 0 ? "" : ((r.critical_count ?? 0) > 0 ? "badge-CRITICAL" : ((r.high_count ?? 0) > 0 ? "badge-HIGH" : ((r.medium_count ?? 0) > 0 ? "badge-MEDIUM" : "badge-LOW")));
    const badgeStyle = count === 0 ? 'style="margin-left: auto; background-color: rgba(16, 185, 129, 0.15); color: #10b981;"' : 'style="margin-left: auto;"';

    runsHtml += `
      <a href="#/run/${r.project}/${r.job}/${r.run_id}" class="nav-item nav-subitem" id="nav-run-${r.run_id}">
        <span title="${r.run_id}">${shortId}</span>
        <span class="badge ${badgeClass}" ${badgeStyle}>${count}</span>
      </a>`;
  });
  if (runsContainer) runsContainer.innerHTML = runsHtml;
}

function renderEmptyState(title, subtitle) {
  return `
    <div class="empty-state">
      <h3>${title}</h3>
      <p>${subtitle}</p>
    </div>`;
}

function handleRoute() {
  const hash = window.location.hash || "#/";
  const viewport = document.getElementById("app-viewport");
  const titleEl = document.getElementById("page-title");

  document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));

  if (dynamicRoutes[hash]) {
    currentRouteParams = {};
    document.getElementById(hash.replace("#/", "nav-"))?.classList.add("active");
    dynamicRoutes[hash](viewport);
    return;
  }

  if (hash === "#/projects") {
    currentRouteParams = {};
    titleEl.textContent = "All Projects";
    document.getElementById("nav-all-projects")?.classList.add("active");
    renderAllProjectsView(viewport);
  } else if (hash === "#/runs") {
    currentRouteParams = {};
    titleEl.textContent = "All Runs";
    document.getElementById("nav-all-runs")?.classList.add("active");
    renderAllRunsView(viewport);
  } else if (hash.startsWith("#/project/")) {
    const projName = hash.replace("#/project/", "");
    currentRouteParams = { proj: projName };
    titleEl.textContent = `Project: ${projName}`;
    document.getElementById(`nav-proj-${projName}`)?.classList.add("active");
    renderProjectView(projName, viewport);
  } else if (hash.startsWith("#/run/")) {
    const pathParts = hash.replace("#/run/", "").split("/");
    if (pathParts.length >= 3) {
      const proj = pathParts[0];
      const job = pathParts[1];
      const runId = pathParts[2];
      const findingIdx = pathParts.length >= 5 && pathParts[3] === "finding" ? parseInt(pathParts[4], 10) : null;

      currentRouteParams = { proj, job, runId, findingIdx };
      titleEl.textContent = `Run: ${proj} / ${job} / ${runId}`;
      document.getElementById(`nav-run-${runId}`)?.classList.add("active");
      renderRunView(proj, job, runId, findingIdx, viewport);
    }
  } else {
    currentRouteParams = {};
    titleEl.textContent = "Global Security Overview";
    document.getElementById("nav-global")?.classList.add("active");
    renderGlobalView(viewport);
  }
}

function renderRunBadge(r) {
  const count = r.vuln_count ?? 0;
  if (count === 0) {
    return `<span class="badge" style="background-color: rgba(16, 185, 129, 0.15); color: #10b981;">0 Findings</span>`;
  }
  if ((r.critical_count ?? 0) > 0) return `<span class="badge badge-CRITICAL">${count} Findings</span>`;
  if ((r.high_count ?? 0) > 0) return `<span class="badge badge-HIGH">${count} Findings</span>`;
  if ((r.medium_count ?? 0) > 0) return `<span class="badge badge-MEDIUM">${count} Findings</span>`;
  return `<span class="badge badge-LOW">${count} Findings</span>`;
}

async function renderGlobalView(container) {
  const filtered = getFilteredRuns();

  if (!filtered || filtered.length === 0) {
    container.innerHTML = renderEmptyState(
      "No Security Runs Yet",
      "Run a Mjolnir analysis locally to generate scan output under output/v1/runs/."
    );
    return;
  }

  let totalRuns = filtered.length;
  let totalVulns = 0;
  filtered.forEach(r => { totalVulns += (r.vuln_count || 0); });

  // Compute Projects Summary Table Data
  const projMap = {};
  filtered.forEach(r => {
    const p = r.project;
    if (!projMap[p]) {
      projMap[p] = { runs: 0, total: 0, crit: 0, high: 0, med: 0, low: 0 };
    }
    projMap[p].runs += 1;
    projMap[p].total += (r.vuln_count || 0);

    let crit = r.critical_count ?? 0;
    let high = r.high_count ?? 0;
    let med = r.medium_count ?? 0;
    let low = r.low_count ?? 0;

    if (Array.isArray(r.vulnerabilities) && r.vulnerabilities.length > 0) {
      crit = 0; high = 0; med = 0; low = 0;
      r.vulnerabilities.forEach(v => {
        const sev = (v.severity || '').toString().toUpperCase();
        if (sev === 'CRITICAL') crit += 1;
        else if (sev === 'HIGH') high += 1;
        else if (sev === 'MEDIUM') med += 1;
        else if (sev === 'LOW') low += 1;
      });
    }

    projMap[p].crit += crit;
    projMap[p].high += high;
    projMap[p].med += med;
    projMap[p].low += low;
  });

  const projRowsHtml = Object.keys(projMap).sort().map(pName => {
    const p = projMap[pName];
    return `
      <tr class="clickable-row" onclick="window.location.hash='#/project/${pName}'">
        <td><strong>${pName}</strong></td>
        <td>${p.runs}</td>
        <td>${p.total}</td>
        <td style="color: var(--severity-critical); font-weight: 600;">${p.crit}</td>
        <td style="color: var(--severity-high); font-weight: 600;">${p.high}</td>
        <td style="color: var(--severity-medium); font-weight: 600;">${p.med}</td>
        <td style="color: var(--severity-low); font-weight: 600;">${p.low}</td>
      </tr>`;
  }).join("");

  // Recent Runs Table Data
  const recentRowsHtml = filtered.map(r => `
    <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'">
      <td><strong>${r.project}</strong></td>
      <td>${r.job}</td>
      <td><code>${r.run_id}</code></td>
      <td>${renderRunBadge(r)}</td>
      <td>${r.timestamp || 'N/A'}</td>
    </tr>
  `).join("");

  container.innerHTML = `
    <div class="metrics-grid">
      <div class="metric-card">
        <span class="metric-label">Analyzed Runs</span>
        <span class="metric-value">${totalRuns}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">Open Findings</span>
        <span class="metric-value" style="color: var(--severity-high);">${totalVulns}</span>
      </div>
    </div>

    <!-- Vulnerability Flow Sankey Card -->
    <div class="card">
      <div class="card-title">Vulnerability Flow Analysis</div>
      <div id="sankey-chart-container"></div>
    </div>

    <!-- Projects Summary Card -->
    <div class="card">
      <div class="card-title">Projects Summary</div>
      <div class="table-container" style="margin-bottom: 0;">
        <table>
          <thead>
            <tr>
              <th>Project</th>
              <th>Total Runs</th>
              <th>Findings</th>
              <th style="color: var(--severity-critical)">Crit</th>
              <th style="color: var(--severity-high)">High</th>
              <th style="color: var(--severity-medium)">Med</th>
              <th style="color: var(--severity-low)">Low</th>
            </tr>
          </thead>
          <tbody>
            ${projRowsHtml}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Recent Runs Card -->
    <div class="card">
      <div class="card-title">Recent Scan Runs</div>
      <div class="table-container" style="margin-bottom: 0;">
        <table>
          <thead>
            <tr>
              <th>Project</th>
              <th>Job Target</th>
              <th>Run Directory</th>
              <th>Findings</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            ${recentRowsHtml}
          </tbody>
        </table>
      </div>
    </div>`;

  const flowJson = await apiComputeSankeyFlow(JSON.stringify(runsState), hideTests);
  renderSankeyChart("sankey-chart-container", flowJson);
}

function renderAllProjectsView(container) {
  const filtered = getFilteredRuns();
  if (!filtered || filtered.length === 0) {
    container.innerHTML = renderEmptyState("No Projects Found", "No active security projects found in output/v1/runs/.");
    return;
  }

  const projMap = {};
  filtered.forEach(r => {
    const p = r.project;
    if (!projMap[p]) projMap[p] = [];
    projMap[p].push(r);
  });

  const cardsHtml = Object.keys(projMap).sort().map(pName => {
    const pRuns = projMap[pName];
    let totalVulns = 0;
    let crit = 0, high = 0, med = 0, low = 0;
    pRuns.forEach(r => {
      totalVulns += (r.vuln_count || 0);
      crit += (r.critical_count || 0);
      high += (r.high_count || 0);
      med += (r.medium_count || 0);
      low += (r.low_count || 0);
    });

    const badgeClass = totalVulns === 0 ? "" : (crit > 0 ? "badge-CRITICAL" : (high > 0 ? "badge-HIGH" : (med > 0 ? "badge-MEDIUM" : "badge-LOW")));
    const badgeStyle = totalVulns === 0 ? 'style="background-color: rgba(16, 185, 129, 0.15); color: #10b981;"' : '';

    return `
      <div class="card clickable-row" onclick="window.location.hash='#/project/${pName}'" style="cursor: pointer;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
          <h3 style="font-size: 18px; font-weight: 600; color: var(--text-primary);">${pName}</h3>
          <span class="badge ${badgeClass}" ${badgeStyle}>${totalVulns} Findings</span>
        </div>
        <div style="display: flex; gap: 24px; color: var(--text-secondary); font-size: 14px;">
          <div><strong>${pRuns.length}</strong> Total Runs</div>
          <div>Latest Run: <code>${pRuns[0]?.run_id || 'N/A'}</code></div>
        </div>
      </div>`;
  }).join("");

  container.innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px;">
      ${cardsHtml}
    </div>`;
}

function renderAllRunsView(container) {
  const filtered = getFilteredRuns();
  if (!filtered || filtered.length === 0) {
    container.innerHTML = renderEmptyState("No Runs Found", "No analysis runs found in output/v1/runs/.");
    return;
  }

  const rowsHtml = filtered.map(r => {
    const count = r.vuln_count ?? 0;
    const badgeClass = count === 0 ? "" : ((r.critical_count ?? 0) > 0 ? "badge-CRITICAL" : ((r.high_count ?? 0) > 0 ? "badge-HIGH" : ((r.medium_count ?? 0) > 0 ? "badge-MEDIUM" : "badge-LOW")));
    const badgeStyle = count === 0 ? 'style="background-color: rgba(16, 185, 129, 0.15); color: #10b981;"' : '';

    return `
      <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'">
        <td><strong>${r.project}</strong></td>
        <td>${r.job}</td>
        <td><code>${r.run_id}</code></td>
        <td><span class="badge ${badgeClass}" ${badgeStyle}>${count} Findings</span></td>
        <td>${r.timestamp || 'N/A'}</td>
      </tr>`;
  }).join("");

  container.innerHTML = `
    <div class="card">
      <div class="card-title">All Executed Runs (${filtered.length})</div>
      <div class="table-container" style="margin-bottom: 0;">
        <table>
          <thead>
            <tr>
              <th>Project</th>
              <th>Job Target</th>
              <th>Run Directory</th>
              <th>Findings</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>
    </div>`;
}

async function renderProjectView(projName, container) {
  const projRuns = runsState.filter(r => r.project === projName);

  if (!projRuns || projRuns.length === 0) {
    container.innerHTML = renderEmptyState(
      "No Runs Yet",
      `No analysis runs found for project ${projName}.`
    );
    return;
  }

  let totalVulns = 0;
  projRuns.forEach(r => totalVulns += (r.vuln_count || 0));

  let rowsHtml = projRuns.map(r => {
    const count = r.vuln_count ?? 0;
    const badgeClass = count === 0 ? "" : ((r.critical_count ?? 0) > 0 ? "badge-CRITICAL" : ((r.high_count ?? 0) > 0 ? "badge-HIGH" : ((r.medium_count ?? 0) > 0 ? "badge-MEDIUM" : "badge-LOW")));
    const badgeStyle = count === 0 ? 'style="background-color: rgba(16, 185, 129, 0.15); color: #10b981;"' : '';

    return `
      <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'">
        <td><strong>${r.job}</strong></td>
        <td><code>${r.run_id}</code></td>
        <td><span class="badge ${badgeClass}" ${badgeStyle}>${count} Findings</span></td>
        <td>${r.timestamp || 'N/A'}</td>
      </tr>`;
  }).join("");

  container.innerHTML = `
    <div class="metrics-grid">
      <div class="metric-card">
        <span class="metric-label">Project Runs</span>
        <span class="metric-value">${projRuns.length}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">Total Open Findings</span>
        <span class="metric-value" style="color: var(--severity-high);">${totalVulns}</span>
      </div>
    </div>

    <!-- Project Specific Vulnerability Flow Sankey Card -->
    <div class="card">
      <div class="card-title">Vulnerability Flow Analysis</div>
      <div id="project-sankey-chart-container"></div>
    </div>

    <div class="card">
      <div class="card-title">Job Targets & Analysis Runs</div>
      <div class="table-container" style="margin-bottom: 0;">
        <table>
          <thead>
            <tr>
              <th>Job Target</th>
              <th>Run Directory</th>
              <th>Findings</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>
    </div>`;

  const flowJson = await apiComputeProjectSankeyFlow(JSON.stringify(runsState), projName);
  renderSankeyChart("project-sankey-chart-container", flowJson);
}

async function renderRunView(proj, job, runId, deepLinkFindingIdx, container) {
  container.innerHTML = `
    <div class="empty-state">
      <h3>Fetching Run Details</h3>
      <p>Loading finding telemetry for ${proj} / ${job}</p>
    </div>`;

  try {
    const res = await fetch(getApiEndpoint(`api/run/${proj}/${job}/${runId}`));
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const data = await res.json();

    const vulnsJson = JSON.stringify(data.vulnerabilities || []);
    currentRunVulns = data.vulnerabilities || [];
    const meta = data.metadata || {};
    const tokenUsage = data.token_usage || {};
    const toolUsage = data.tool_usage || {};
    const errorsGrouped = tokenUsage.errors_grouped || {};
    const errorKeys = Object.keys(errorsGrouped);

    let errorsHtml = "";
    if (errorKeys.length > 0) {
      const errorItems = errorKeys.map(k => `<li><strong>${k}</strong>: ${errorsGrouped[k]} error(s)</li>`).join("");
      errorsHtml = `
        <div class="run-errors-card">
          <h4>Run Errors & Telemetry Warnings</h4>
          <ul class="run-errors-list">${errorItems}</ul>
        </div>`;
    }

    let toolUsageHtml = "";
    if (toolUsage.by_tool && Object.keys(toolUsage.by_tool).length > 0) {
      const tot = toolUsage.total || {};
      const toolRows = Object.entries(toolUsage.by_tool).map(([toolName, stats]) => `
        <tr>
          <td><code>${toolName}</code></td>
          <td>${stats.calls}</td>
          <td style="color: var(--status-resolved);">${stats.successes}</td>
          <td style="color: ${stats.failures > 0 ? 'var(--severity-critical)' : 'inherit'};">${stats.failures}</td>
          <td><span class="badge ${stats.failures > 0 ? 'badge-critical' : 'badge-low'}">${stats.failure_rate}</span></td>
        </tr>
      `).join("");

      toolUsageHtml = `
        <div class="card" style="margin-bottom: 20px;">
          <div class="card-title" style="display: flex; justify-content: space-between; align-items: center;">
            <span>Tool Usage Telemetry</span>
            <span style="font-size: 13px; font-weight: normal;">Total Calls: <strong>${tot.total_calls || 0}</strong> | Failure Rate: <strong>${tot.failure_rate || '0.00%'}</strong></span>
          </div>
          <table class="findings-table">
            <thead>
              <tr>
                <th>Tool Name</th>
                <th>Calls</th>
                <th>Successes</th>
                <th>Failures</th>
                <th>Failure Rate</th>
              </tr>
            </thead>
            <tbody>
              ${toolRows}
            </tbody>
          </table>
        </div>`;
    }

    const shortCommit = (meta.target_commit || meta.commit || 'N/A').substring(0, 8);
    const statusStr = meta.status || 'Success';
    const statusColor = statusStr === 'Failed' ? 'var(--severity-critical)' : 'var(--status-resolved)';

    // Strict WASM Summary Calculation via Worker Thread
    const summaryRaw = await apiComputeSummary(vulnsJson);
    const summary = JSON.parse(summaryRaw);

    container.innerHTML = `
      <div class="run-meta-grid">
        <div class="run-meta-item">Project: <strong>${proj}</strong></div>
        <div class="run-meta-item">Job: <strong>${job}</strong></div>
        <div class="run-meta-item">Model: <strong>${meta.model || 'Unknown'}</strong></div>
        <div class="run-meta-item">Commit: <code>${shortCommit}</code></div>
        <div class="run-meta-item">Mode: <strong>${meta.mode || 'Discovery'}</strong></div>
        <div class="run-meta-item">Status: <strong style="color: ${statusColor};">${statusStr}</strong></div>
        <div class="run-meta-item">Scan Time: <strong>${meta.timestamp || 'N/A'}</strong></div>
      </div>

      ${errorsHtml}

      ${toolUsageHtml}

      <div class="metrics-grid">
        <div class="metric-card">
          <span class="metric-label">Total Findings</span>
          <span class="metric-value">${summary.total}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Critical</span>
          <span class="metric-value" style="color: var(--severity-critical);">${summary.critical}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">High</span>
          <span class="metric-value" style="color: var(--severity-high);">${summary.high}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Medium</span>
          <span class="metric-value" style="color: var(--severity-medium);">${summary.medium}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Low</span>
          <span class="metric-value" style="color: var(--severity-low);">${summary.low}</span>
        </div>
      </div>

      <!-- Run Specific Vulnerability Flow Sankey Card -->
      <div class="card">
        <div class="card-title">Vulnerability Flow Analysis</div>
        <div id="run-sankey-chart-container"></div>
      </div>

      <div class="toolbar">
        <input type="text" id="search-input" class="search-input" placeholder="Filter findings (Press '/' to focus)...">
        <select id="severity-select" class="select-input">
          <option value="ALL">All Severities</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
        <select id="status-select" class="select-input">
          <option value="all" selected>All Statuses</option>
          <option value="open">Open</option>
          <option value="closed">Closed / Resolved</option>
        </select>
        <select id="sort-select" class="select-input">
          <option value="sev-desc" selected>Sort: Severity High-Low</option>
          <option value="sev-asc">Sort: Severity Low-High</option>
          <option value="title">Sort: Title (A-Z)</option>
          <option value="file">Sort: File Location</option>
        </select>
        <select id="view-mode-select" class="select-input">
          <option value="list" selected>View: Table</option>
          <option value="tree">View: Tree</option>
        </select>
        <button id="btn-export-json" class="btn btn-secondary">Export JSON</button>
        <button id="btn-export-md" class="btn btn-secondary">Export Markdown</button>
      </div>

      <div id="findings-content-container">
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Title</th>
                <th>File Location</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody id="vuln-table-body">
              <!-- Filtered Rows Injected Here -->
            </tbody>
          </table>
        </div>
      </div>`;

    apiComputeRunSankeyFlow(vulnsJson).then(runFlowJson => {
      renderSankeyChart("run-sankey-chart-container", runFlowJson);
    });

    const searchInput = document.getElementById("search-input");
    const severitySelect = document.getElementById("severity-select");
    const statusSelect = document.getElementById("status-select");
    const sortSelect = document.getElementById("sort-select");
    const viewModeSelect = document.getElementById("view-mode-select");

    function renderStatusBadge(status) {
      const s = (status || 'Open').toString().trim();
      const lower = s.toLowerCase();
      if (lower === 'open') {
        return `<span class="badge" style="background-color: rgba(244, 63, 94, 0.15); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.3);">${s}</span>`;
      } else if (lower === 'closed' || lower === 'resolved' || lower === 'fixed') {
        return `<span class="badge" style="background-color: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3);">${s}</span>`;
      } else {
        return `<span class="badge" style="background-color: rgba(113, 113, 122, 0.15); color: #a1a1aa; border: 1px solid rgba(113, 113, 122, 0.3);">${s}</span>`;
      }
    }

    let currentFilterReqId = 0;
    async function updateTable() {
      const reqId = ++currentFilterReqId;
      const query = searchInput.value;
      const severity = severitySelect.value;
      const status = statusSelect.value;
      const sortOrder = sortSelect.value;
      const viewMode = viewModeSelect.value;

      // Off-thread WASM Filter & Sort Execution via Worker
      const filteredRaw = await apiFilterVulnerabilities(vulnsJson, query, severity, status, sortOrder);
      if (reqId !== currentFilterReqId) return;

      const filtered = JSON.parse(filteredRaw);
      window.currentFiltered = filtered;

      const containerEl = document.getElementById("findings-content-container");

      if (viewMode === "tree") {
        containerEl.innerHTML = renderTreeView(filtered);
      } else {
        containerEl.innerHTML = `
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Title</th>
                  <th>File Location</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody id="vuln-table-body">
                ${(!filtered || filtered.length === 0)
                  ? `<tr><td colspan="4" style="text-align:center; color: var(--text-muted); padding: 30px;">No matching findings found.</td></tr>`
                  : filtered.map((v, idx) => `
                    <tr class="clickable-row" onclick="window.showFindingModal(${idx})">
                      <td><span class="badge badge-${v.severity || 'LOW'}">${v.severity || 'LOW'}</span></td>
                      <td><strong>${v.title || 'Untitled Security Finding'}</strong></td>
                      <td><code>${v.file || ''}${v.location ? ':' + v.location : ''}</code></td>
                      <td>${renderStatusBadge(v.status)}</td>
                    </tr>
                  `).join("")
                }
              </tbody>
            </table>
          </div>`;
      }
    }

    searchInput.addEventListener("input", updateTable);
    severitySelect.addEventListener("change", updateTable);
    statusSelect.addEventListener("change", updateTable);
    sortSelect.addEventListener("change", updateTable);
    viewModeSelect.addEventListener("change", updateTable);

    document.getElementById("btn-export-json").addEventListener("click", () => {
      downloadFile(`${proj}_${job}_${runId}_findings.json`, JSON.stringify(window.currentFiltered || currentRunVulns, null, 2), "application/json");
    });

    document.getElementById("btn-export-md").addEventListener("click", () => {
      const mdContent = generateMarkdownReport(proj, job, runId, window.currentFiltered || currentRunVulns);
      downloadFile(`${proj}_${job}_${runId}_report.md`, mdContent, "text/markdown");
    });

    window.showFindingModal = function(idx) {
      const v = window.currentFiltered[idx];
      if (!v) return;

      // Deep Link URL Hash Update
      const deepLinkHash = `#/run/${proj}/${job}/${runId}/finding/${idx}`;
      if (window.location.hash !== deepLinkHash) {
        history.replaceState(null, "", deepLinkHash);
      }

      document.getElementById("modal-title").textContent = v.title || "Finding Details";
      document.getElementById("modal-body").innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
          <div>
            <span class="badge badge-${v.severity}">${v.severity}</span>
            <code style="margin-left: 8px;">${v.file || ''}${v.location ? ':' + v.location : ''}</code>
          </div>
          <button id="btn-copy-finding-link" class="btn btn-secondary" style="font-size: 0.75rem;">Copy Direct Link</button>
        </div>
        <h4 style="margin-bottom: 6px; font-weight: 600;">Description</h4>
        <p style="color: var(--text-secondary); margin-bottom: 16px;">${v.description || 'No description provided.'}</p>

        <h4 style="margin-bottom: 6px; font-weight: 600;">Recommendation</h4>
        <p style="color: var(--text-secondary);">${v.recommendation || 'No recommendation provided.'}</p>
      `;

      document.getElementById("btn-copy-finding-link").addEventListener("click", () => {
        navigator.clipboard.writeText(window.location.href);
        const btn = document.getElementById("btn-copy-finding-link");
        btn.textContent = "Copied!";
        setTimeout(() => { btn.textContent = "Copy Direct Link"; }, 2000);
      });

      document.getElementById("vulnerability-modal").classList.remove("hidden");
    };

    updateTable();

    // Auto open modal if deep linked to finding index
    if (deepLinkFindingIdx !== null && !isNaN(deepLinkFindingIdx) && window.currentFiltered[deepLinkFindingIdx]) {
      window.showFindingModal(deepLinkFindingIdx);
    }

  } catch (err) {
    container.innerHTML = renderEmptyState(
      "Failed to Load Run",
      err.message || "Could not retrieve run finding telemetry."
    );
  }
}

function renderTreeView(findings) {
  if (!findings || findings.length === 0) {
    return `<div style="text-align:center; color: var(--text-muted); padding: 30px;">No matching findings found.</div>`;
  }
  const tree = {};
  findings.forEach((v, idx) => {
    const filePath = v.file || "Unspecified File";
    const parts = filePath.split("/");
    let curr = tree;
    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      if (!curr[part]) curr[part] = { _dirs: {}, _files: [] };
      curr = curr[part]._dirs;
    }
    const filename = parts[parts.length - 1];
    if (!curr[filename]) curr[filename] = { _dirs: {}, _files: [] };
    curr[filename]._files.push({ vuln: v, originalIdx: idx });
  });

  function buildHtml(node) {
    let html = "";
    for (const key of Object.keys(node).sort()) {
      const d = node[key];
      html += `<div class="tree-folder">
        <div class="tree-folder-title">${key}</div>
        <div class="tree-children">`;
      for (const f of d._files) {
        const v = f.vuln;
        html += `
          <div class="tree-file-item" onclick="window.showFindingModal(${f.originalIdx})">
            <div>
              <span class="badge badge-${v.severity}">${v.severity}</span>
              <strong style="margin-left: 8px;">${v.title}</strong>
            </div>
            <code>${v.location ? ':' + v.location : ''}</code>
          </div>`;
      }
      html += buildHtml(d._dirs);
      html += `</div></div>`;
    }
    return html;
  }

  return `<div class="tree-container">${buildHtml(tree)}</div>`;
}

function downloadFile(filename, text, mimeType) {
  const element = document.createElement('a');
  element.setAttribute('href', `data:${mimeType};charset=utf-8,` + encodeURIComponent(text));
  element.setAttribute('download', filename);
  element.style.display = 'none';
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
}

function generateMarkdownReport(proj, job, runId, vulns) {
  let md = `# Security Audit Report: ${proj} / ${job}\n\n`;
  md += `- **Run Identifier**: \`${runId}\`\n`;
  md += `- **Total Findings Reported**: ${vulns.length}\n\n`;
  md += `## Findings Summary\n\n`;

  vulns.forEach((v, idx) => {
    md += `### ${idx + 1}. [${v.severity}] ${v.title}\n`;
    md += `- **Location**: \`${v.file}${v.location ? ':' + v.location : ''}\`\n`;
    md += `- **Status**: ${v.status}\n\n`;
    md += `**Description**:\n${v.description}\n\n`;
    md += `**Recommendation**:\n${v.recommendation}\n\n`;
    md += `---\n\n`;
  });

  return md;
}

function renderSankeyChart(containerId, flowJson) {
  window.lastSankeyState = { containerId, flowJson };

  const container = document.getElementById(containerId);
  if (!container) return;

  const flowRows = JSON.parse(flowJson || "[]");

  if (!flowRows || flowRows.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted); text-align: center; padding: 30px 0;">No flow data available.</div>`;
    return;
  }

  if (window.google && window.google.visualization && window.google.visualization.Sankey) {
    drawGoogleSankey(flowRows, container);
  } else if (window.google && window.google.charts) {
    window.google.charts.setOnLoadCallback(() => drawGoogleSankey(flowRows, container));
  } else {
    container.innerHTML = `<div style="color: var(--text-muted); text-align: center; padding: 30px 0;">Flow chart ready.</div>`;
  }
}

function drawGoogleSankey(rows, container) {
  try {
    if (!rows || rows.length === 0) {
      container.innerHTML = `
        <div style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--text-muted); padding: 30px 0;">
          Flow history requires at least 2 analysis phases to render.
        </div>`;
      return;
    }

    const data = new window.google.visualization.DataTable();
    data.addColumn('string', 'From');
    data.addColumn('string', 'To');
    data.addColumn('number', 'Weight');
    data.addRows(rows);

    // Extract unique nodes in order of appearance
    const uniqueNodes = [];
    const nodesPerPrefix = {};
    let maxNodesInColumn = 1;

    rows.forEach(row => {
      if (!uniqueNodes.includes(row[0])) uniqueNodes.push(row[0]);
      if (!uniqueNodes.includes(row[1])) uniqueNodes.push(row[1]);
    });

    uniqueNodes.forEach(node => {
      const parts = node.split(' - ');
      const prefix = parts.length > 1 ? parts.slice(0, -1).join(' - ') : 'default';
      nodesPerPrefix[prefix] = (nodesPerPrefix[prefix] || 0) + 1;
      if (nodesPerPrefix[prefix] > maxNodesInColumn) {
        maxNodesInColumn = nodesPerPrefix[prefix];
      }
    });

    const calculatedHeight = Math.max(320, (maxNodesInColumn * 42) + 40);
    container.style.height = calculatedHeight + 'px';

    // Map severity names to matching theme colors
    const nodeColors = uniqueNodes.map(nodeName => {
      if (nodeName.includes('Critical')) return '#ef4444';
      if (nodeName.includes('High')) return '#f97316';
      if (nodeName.includes('Medium')) return '#eab308';
      if (nodeName.includes('Low')) return '#3b82f6';
      if (nodeName.includes('Informational')) return '#38bdf8';
      if (nodeName.includes('Closed') || nodeName.includes('Skipped') || nodeName.includes('Excluded')) return '#71717a';
      return '#38bdf8';
    });

    const targetWidth = container.clientWidth ? (container.clientWidth - 4) : '100%';

    const options = {
      width: targetWidth,
      height: calculatedHeight,
      sankey: {
        iterations: 0,
        node: {
          colors: nodeColors,
          nodePadding: 16,
          width: 18,
          label: {
            fontName: 'Segoe UI',
            fontSize: 12,
            color: '#f4f4f5',
            bold: true
          }
        },
        link: {
          colorMode: 'gradient'
        }
      }
    };

    const chart = new window.google.visualization.Sankey(container);
    chart.draw(data, options);
  } catch (e) {
    console.warn("Google Sankey draw failed:", e);
  }
}

let sankeyResizeTimer = null;
window.addEventListener('resize', () => {
  clearTimeout(sankeyResizeTimer);
  sankeyResizeTimer = setTimeout(() => {
    if (window.lastSankeyState) {
      renderSankeyChart(window.lastSankeyState.containerId, window.lastSankeyState.flowJson);
    }
  }, 150);
});

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrap);
} else {
  bootstrap();
}
