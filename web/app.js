// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

import init, {
  compute_summary,
  filter_vulnerabilities,
  compute_sankey_flow,
  compute_project_sankey_flow,
  compute_run_sankey_flow,
  generate_report
} from './dist/mjolnir_dashboard_wasm.js';
import { registerTokenUsageModule, renderProjectTokenUsage, renderRunTokenUsage } from './dist/token_usage_module.js';
import { registerToolUsageModule, renderProjectToolUsage, renderRunToolUsage } from './dist/tool_usage_module.js';
import { BUILD_TIMESTAMP } from './dist/build_info.js';
import { API_VERSION, RUNS_SUBDIR, WEB_SUBDIR } from './constants.js';



export function getAssetUrl(path) {
  let base = window.location.pathname;
  if (base.endsWith(".html") || base.endsWith(".htm")) {
    base = base.substring(0, base.lastIndexOf("/") + 1);
  }
  if (!base.endsWith("/")) {
    base += "/";
  }
  const cleanPath = path.replace(/^\//, "");
  return new URL(cleanPath, window.location.origin + base).href;
}

export function formatLocalTimestamp(ts) {
  if (!ts) return "N/A";
  const normalized = ts.includes(" ") ? ts.replace(" ", "T") + "Z" : ts;
  const d = new Date(normalized);
  return isNaN(d.getTime()) ? ts : d.toLocaleString(undefined, { timeZoneName: "short" });
}

export function parseRunTime(r) {
  if (!r) return 0;
  if (r.timestamp && r.timestamp !== "N/A" && r.timestamp !== "Unknown") {
    const normalized = r.timestamp.includes(" ") ? r.timestamp.replace(" ", "T") + "Z" : r.timestamp;
    const d = new Date(normalized);
    if (!isNaN(d.getTime())) return d.getTime();
  }
  const match = String(r.run_id || "").match(/(\d{4})(\d{2})(\d{2})_?(\d{2})(\d{2})(\d{2})/);
  if (match) {
    return Date.UTC(
      parseInt(match[1], 10),
      parseInt(match[2], 10) - 1,
      parseInt(match[3], 10),
      parseInt(match[4], 10),
      parseInt(match[5], 10),
      parseInt(match[6], 10)
    );
  }
  return 0;
}

export function renderTriggerBadge(triggerStr) {
  if (!triggerStr) return "";
  const t = triggerStr.trim().toLowerCase();
  if (!t) return "";
  if (t === "ci") {
    return `<span class="trigger-pill trigger-pill-ci">CI/CD</span>`;
  }
  if (t === "automated") {
    return `<span class="trigger-pill trigger-pill-automated">Automated</span>`;
  }
  if (t === "manual") {
    return `<span class="trigger-pill trigger-pill-manual">Manual</span>`;
  }
  const display = triggerStr.length > 12 ? triggerStr.substring(0, 12) : triggerStr;
  return `<span class="trigger-pill trigger-pill-unknown">${display}</span>`;
}

let dynamicRoutes = {};

let runsState = [];
let currentRunVulns = [];
let currentRouteParams = {};

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
    mainWasmPromise = init({ module_or_path: getAssetUrl('web/dist/mjolnir_dashboard_wasm_bg.wasm') }).catch(err => {
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

async function workerFilterVulnerabilities(vulnerabilitiesJson, query, severityFilter, statusFilter, sortOrder) {
  return runWorkerTask('filter_vulnerabilities', { vulnerabilitiesJson, query, severityFilter, statusFilter, sortOrder });
}

async function workerComputeSankeyFlow(runsJson, hideTests) {
  return runWorkerTask('compute_sankey_flow', { runsJson, hideTests });
}

async function workerComputeProjectSankeyFlow(runsJson, targetProject) {
  return runWorkerTask('compute_project_sankey_flow', { runsJson, targetProject });
}

async function workerComputeRunSankeyFlow(vulnerabilitiesJson) {
  return runWorkerTask('compute_run_sankey_flow', { vulnerabilitiesJson });
}

async function workerComputeSummary(vulnerabilitiesJson) {
  return runWorkerTask('compute_summary', { vulnerabilitiesJson });
}

async function bootstrap() {
  setupEventListeners();
  const navContainer = document.querySelector(".sidebar-nav");
  registerTokenUsageModule(navContainer, dynamicRoutes, renderEmptyState, getFilteredRuns);
  registerToolUsageModule(navContainer, dynamicRoutes, renderEmptyState, getFilteredRuns);

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
      closeModal();
    }
  });

  document.getElementById("modal-close")?.addEventListener("click", closeModal);
  document.getElementById("vulnerability-modal")?.addEventListener("click", (e) => {
    if (e.target.id === "vulnerability-modal") {
      closeModal();
    }
  });
}

export function openModal(title, bodyHtml) {
  const modal = document.getElementById("vulnerability-modal");
  if (!modal) return;
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-body").innerHTML = bodyHtml;
  modal.classList.remove("hidden");
}

export function closeModal() {
  const modal = document.getElementById("vulnerability-modal");
  if (!modal) return;
  modal.classList.add("hidden");
  if (currentRouteParams.proj && currentRouteParams.job && currentRouteParams.runId) {
    // Restore run hash without finding suffix
    const runHash = `#/run/${currentRouteParams.proj}/${currentRouteParams.job}/${currentRouteParams.runId}`;
    if (window.location.hash !== runHash && window.location.hash.includes("/finding/")) {
      history.replaceState(null, "", runHash);
    }
  }
}

window.openModal = openModal;
window.closeModal = closeModal;

async function fetchRunsData() {
  runsState = await fetchRunsFromGcsBucket();
  updateFooterTimestamp();
  renderSidebarNavigation();
}

async function fetchRunsFromGcsBucket() {
  try {
    let basePath = window.location.pathname;
    if (basePath.endsWith(".html") || basePath.endsWith(".htm")) {
      basePath = basePath.substring(0, basePath.lastIndexOf("/") + 1);
    }
    if (!basePath.endsWith("/")) {
      basePath += "/";
    }
    const cleanBasePath = basePath.replace(/^\//, "");
    const listUrl = new URL(`${cleanBasePath}?prefix=${RUNS_SUBDIR}/`, window.location.origin).href;
    const res = await fetch(listUrl);

    if (!res.ok) return [];

    const text = await res.text();
    const parser = new DOMParser();
    const xml = parser.parseFromString(text, "text/xml");

    const keys = Array.from(xml.getElementsByTagNameNS("*", "Key"))
      .map(node => node.textContent)
      .filter(key => key && key.endsWith("/metadata.json"));

    if (keys.length === 0) return [];

    const runPromises = keys.map(async (key) => {
      try {
        const metaRes = await fetch(getAssetUrl(key));
        if (!metaRes.ok) return null;
        const meta = await metaRes.json();

        const vulnKey = key.replace("metadata.json", "vulnerabilities.json");
        const vulnRes = await fetch(getAssetUrl(vulnKey));
        const vulns = vulnRes.ok ? await vulnRes.json() : [];

        const tokenKey = key.replace("metadata.json", "token_usage.json");
        const tokenRes = await fetch(getAssetUrl(tokenKey));
        const token_usage = tokenRes.ok ? await tokenRes.json() : {};

        const toolKey = key.replace("metadata.json", "tool_usage.json");
        const toolRes = await fetch(getAssetUrl(toolKey));
        const tool_usage = toolRes.ok ? await toolRes.json() : {};

        const parts = key.split("/");
        const project = meta.project || parts[2] || "default";
        const job = meta.job || parts[3] || "default";
        const run_id = meta.run_id || parts[4] || "unknown";

        let critical = 0, high = 0, medium = 0, low = 0, open_count = 0, closed_count = 0;
        if (Array.isArray(vulns)) {
          vulns.forEach(v => {
            const sev = String(v.severity || v.severity_level || "LOW").toUpperCase();
            if (sev === "CRITICAL") critical++;
            else if (sev === "HIGH") high++;
            else if (sev === "MEDIUM") medium++;
            else low++;

            const st = String(v.status || v.state || "Open").toLowerCase();
            if (["closed", "fixed", "resolved"].includes(st)) closed_count++;
            else open_count++;
          });
        }

        return {
          project,
          job,
          run_id,
          timestamp: meta.timestamp || run_id,
          vuln_count: Array.isArray(vulns) ? vulns.length : 0,
          critical_count: critical,
          high_count: high,
          medium_count: medium,
          low_count: low,
          open_count,
          closed_count,
          vulnerabilities: Array.isArray(vulns) ? vulns : [],
          token_usage,
          tool_usage,
          model: meta.model || "Unknown",
          commit: meta.target_commit || "Unknown",
          mode: meta.mode || "Discovery",
          pr: meta.pr || null,
          trigger: meta.trigger || "",
          status: meta.status || "Success",
        };
      } catch (err) {
        return null;
      }
    });

    const results = await Promise.all(runPromises);
    const valid = results.filter(Boolean);
    valid.sort((a, b) => parseRunTime(b) - parseRunTime(a) || String(b.run_id).localeCompare(String(a.run_id)));
    return valid;
  } catch (err) {
    console.warn("GCS Bucket list fetch failed:", err);
    return [];
  }
}

function getFilteredRuns() {
  return runsState || [];
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
    const triggerBadge = renderTriggerBadge(r.trigger);
    const timeFormatted = formatLocalTimestamp(r.timestamp);
    const runLabel = `${r.project} (${timeFormatted})`;
    const count = r.vuln_count ?? 0;
    const badgeClass = count === 0 ? "" : ((r.critical_count ?? 0) > 0 ? "badge-CRITICAL" : ((r.high_count ?? 0) > 0 ? "badge-HIGH" : ((r.medium_count ?? 0) > 0 ? "badge-MEDIUM" : "badge-LOW")));
    const badgeStyle = count === 0 ? 'style="margin-left: auto; background-color: rgba(16, 185, 129, 0.15); color: #10b981;"' : 'style="margin-left: auto;"';

    runsHtml += `
      <a href="#/run/${r.project}/${r.job}/${r.run_id}" class="nav-item nav-subitem" id="nav-run-${r.run_id}">
        <span title="${r.project} / ${r.job} / ${r.run_id} (${timeFormatted})">${triggerBadge ? triggerBadge + ' ' : ''}${runLabel}</span>
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
    if (hash === "#/token-usage") {
      titleEl.textContent = "Global Token Usage";
    } else if (hash === "#/tool-usage") {
      titleEl.textContent = "Global Tool Usage";
    }
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
  if ((r.low_count ?? 0) > 0) return `<span class="badge badge-LOW">${count} Findings</span>`;
  return `<span class="badge badge-INFO">${count} Findings</span>`;
}

async function renderGlobalView(container) {
  const filtered = getFilteredRuns();

  if (!filtered || filtered.length === 0) {
    container.innerHTML = renderEmptyState(
      "No Security Runs Yet",
      `Run a Mjolnir analysis locally to generate scan output under output/${RUNS_SUBDIR}/.`
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
      projMap[p] = { runs: 0, total: 0, crit: 0, high: 0, med: 0, low: 0, info: 0, closed: 0 };
    }
    projMap[p].runs += 1;
    projMap[p].total += (r.vuln_count || 0);

    let crit = r.critical_count ?? 0;
    let high = r.high_count ?? 0;
    let med = r.medium_count ?? 0;
    let low = r.low_count ?? 0;
    let info = r.info_count ?? 0;
    let closed = r.closed_count ?? 0;

    if (Array.isArray(r.vulnerabilities) && r.vulnerabilities.length > 0) {
      crit = 0; high = 0; med = 0; low = 0; info = 0; closed = 0;
      r.vulnerabilities.forEach(v => {
        const st = String(v.status || v.state || "Open").toLowerCase();
        if (["closed", "fixed", "resolved"].includes(st)) {
          closed += 1;
          return;
        }
        const sev = (v.severity || '').toString().toUpperCase();
        if (sev === 'CRITICAL') crit += 1;
        else if (sev === 'HIGH') high += 1;
        else if (sev === 'MEDIUM') med += 1;
        else if (sev === 'LOW') low += 1;
        else info += 1;
      });
    }

    projMap[p].crit += crit;
    projMap[p].high += high;
    projMap[p].med += med;
    projMap[p].low += low;
    projMap[p].info += info;
    projMap[p].closed += closed;
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
        <td style="color: var(--severity-info); font-weight: 600;">${p.info}</td>
        <td style="color: var(--text-muted); font-weight: 600;">${p.closed}</td>
      </tr>`;
  }).join("");

  // Recent Runs Table Data
  const recentRowsHtml = filtered.slice(0, 10).map(r => {
    const triggerBadge = renderTriggerBadge(r.trigger);
    return `
    <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'">
      <td><strong>${r.project}</strong>${triggerBadge ? ' ' + triggerBadge : ''}</td>
      <td>${r.job}</td>
      <td><code>${r.run_id}</code></td>
      <td>${renderRunBadge(r)}</td>
      <td><span title="UTC: ${r.timestamp || 'N/A'}">${formatLocalTimestamp(r.timestamp)}</span></td>
    </tr>`;
  }).join("");

  container.innerHTML = `
    <div class="metrics-grid">
      <div class="metric-card">
        <span class="metric-label">Analyzed Runs</span>
        <span class="metric-value">${totalRuns}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">Total Findings</span>
        <span class="metric-value">${totalVulns}</span>
      </div>
    </div>

    <!-- Projects Summary Card -->
    <div class="card">
      <div class="card-title">Projects Breakdown (${Object.keys(projMap).length})</div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Project</th>
              <th>Runs</th>
              <th>Total</th>
              <th style="color: var(--severity-critical);">Crit</th>
              <th style="color: var(--severity-high);">High</th>
              <th style="color: var(--severity-medium);">Med</th>
              <th style="color: var(--severity-low);">Low</th>
              <th style="color: var(--severity-info);">Info</th>
              <th style="color: var(--text-muted);">Closed</th>
            </tr>
          </thead>
          <tbody>
            ${projRowsHtml}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Global Recent Runs Table Card -->
    <div class="card">
      <div class="card-title">Recent Scan Runs</div>
      <div class="table-container" style="margin-bottom: 0;">
        <table>
          <thead>
            <tr>
              <th>Project</th>
              <th>Job Target</th>
              <th>Run Directory</th>
              <th>Status</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            ${recentRowsHtml}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Vulnerability Flow Sankey Card (Lowest Section) -->
    <div class="card">
      <div class="card-title">Vulnerability Flow Analysis</div>
      <div id="sankey-chart-container"></div>
    </div>`;

  const flowJson = await workerComputeSankeyFlow(JSON.stringify(runsState), false);
  renderSankeyChart("sankey-chart-container", flowJson);
}

function renderAllProjectsView(container) {
  const filtered = getFilteredRuns();
  if (!filtered || filtered.length === 0) {
    container.innerHTML = renderEmptyState("No Projects Found", `No analysis runs found in output/${RUNS_SUBDIR}/.`);
    return;
  }

  const projMap = {};
  filtered.forEach(r => {
    const p = r.project || "default";
    if (!projMap[p]) {
      projMap[p] = { runs: 0, vulns: 0, critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    }
    projMap[p].runs++;
    projMap[p].vulns += (r.vuln_count || 0);
    projMap[p].critical += (r.critical_count || 0);
    projMap[p].high += (r.high_count || 0);
    projMap[p].medium += (r.medium_count || 0);
    projMap[p].low += (r.low_count || 0);
  });

  const cardsHtml = Object.keys(projMap).sort().map(pName => {
    const p = projMap[pName];
    return `
      <div class="card clickable-card" onclick="window.location.hash='#/project/${pName}'" style="margin-bottom: 0;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-primary); margin: 0;">${pName}</h3>
          <span class="badge" style="background-color: var(--bg-card);">${p.runs} ${p.runs === 1 ? 'run' : 'runs'}</span>
        </div>
        <div class="metrics-grid" style="grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 0;">
          <div style="background: var(--bg-app); padding: 8px; border-radius: 6px; text-align: center;">
            <div style="font-size: 0.72rem; color: var(--text-secondary);">Findings</div>
            <div style="font-size: 1.1rem; font-weight: 700;">${p.vulns}</div>
          </div>
          <div style="background: var(--bg-app); padding: 8px; border-radius: 6px; text-align: center;">
            <div style="font-size: 0.72rem; color: var(--severity-critical);">Critical</div>
            <div style="font-size: 1.1rem; font-weight: 700; color: var(--severity-critical);">${p.critical}</div>
          </div>
          <div style="background: var(--bg-app); padding: 8px; border-radius: 6px; text-align: center;">
            <div style="font-size: 0.72rem; color: var(--severity-high);">High</div>
            <div style="font-size: 1.1rem; font-weight: 700; color: var(--severity-high);">${p.high}</div>
          </div>
        </div>
      </div>`;
  }).join("");

  container.innerHTML = `
    <div class="card-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px;">
      ${cardsHtml}
    </div>`;
}

function renderAllRunsView(container) {
  const filtered = getFilteredRuns();
  if (!filtered || filtered.length === 0) {
    container.innerHTML = renderEmptyState("No Runs Found", `No analysis runs found in output/${RUNS_SUBDIR}/.`);
    return;
  }

  const rowsHtml = filtered.map(r => {
    const count = r.vuln_count ?? 0;
    const badgeClass = count === 0 ? "" : ((r.critical_count ?? 0) > 0 ? "badge-CRITICAL" : ((r.high_count ?? 0) > 0 ? "badge-HIGH" : ((r.medium_count ?? 0) > 0 ? "badge-MEDIUM" : "badge-LOW")));
    const badgeStyle = count === 0 ? 'style="background-color: rgba(16, 185, 129, 0.15); color: #10b981;"' : '';
    const triggerBadge = renderTriggerBadge(r.trigger);

    return `
      <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'">
        <td><strong>${r.project}</strong>${triggerBadge ? ' ' + triggerBadge : ''}</td>
        <td>${r.job}</td>
        <td><code>${r.run_id}</code></td>
        <td><span class="badge ${badgeClass}" ${badgeStyle}>${count} Findings</span></td>
        <td><span title="UTC: ${r.timestamp || 'N/A'}">${formatLocalTimestamp(r.timestamp)}</span></td>
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
  const projRuns = runsState
    .filter(r => r.project === projName)
    .sort((a, b) => parseRunTime(b) - parseRunTime(a) || String(b.run_id).localeCompare(String(a.run_id)));

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
    const triggerBadge = renderTriggerBadge(r.trigger);

    return `
      <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'">
        <td><strong>${r.job}</strong>${triggerBadge ? ' ' + triggerBadge : ''}</td>
        <td><code>${r.run_id}</code></td>
        <td><span class="badge ${badgeClass}" ${badgeStyle}>${count} Findings</span></td>
        <td><span title="UTC: ${r.timestamp || 'N/A'}">${formatLocalTimestamp(r.timestamp)}</span></td>
      </tr>`;
  }).join("");

  const projectTokenUsageHtml = renderProjectTokenUsage(projRuns);
  const projectToolUsageHtml = renderProjectToolUsage(projRuns);

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
    </div>

    ${projectTokenUsageHtml}

    ${projectToolUsageHtml}`;

  const flowJson = await workerComputeProjectSankeyFlow(JSON.stringify(runsState), projName);
  renderSankeyChart("project-sankey-chart-container", flowJson);
}

async function fetchRunDetailsFromGcs(proj, job, runId) {
  const prefix = `${RUNS_SUBDIR}/${proj}/${job}/${runId}`;
  const [metaRes, vulnRes, tokenRes, toolRes] = await Promise.all([

    fetch(getAssetUrl(`${prefix}/metadata.json`)),
    fetch(getAssetUrl(`${prefix}/vulnerabilities.json`)),
    fetch(getAssetUrl(`${prefix}/token_usage.json`)),
    fetch(getAssetUrl(`${prefix}/tool_usage.json`))
  ]);

  const metadata = metaRes.ok ? await metaRes.json() : {};
  const vulnerabilities = vulnRes.ok ? await vulnRes.json() : [];
  const token_usage = tokenRes.ok ? await tokenRes.json() : {};
  const tool_usage = toolRes.ok ? await toolRes.json() : {};

  return { metadata, vulnerabilities, token_usage, tool_usage };
}

async function renderRunView(proj, job, runId, deepLinkFindingIdx, container) {
  container.innerHTML = `
    <div class="empty-state">
      <h3>Fetching Run Details</h3>
      <p>Loading findings for ${proj} / ${job}</p>
    </div>`;

  try {
    const data = await fetchRunDetailsFromGcs(proj, job, runId);

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
          <h4>Run Errors & Warnings</h4>
          <ul class="run-errors-list">${errorItems}</ul>
        </div>`;
    }

    const tokenUsageHtml = renderRunTokenUsage(data);
    const toolUsageHtml = renderRunToolUsage(data);

    const shortCommit = (meta.target_commit || 'Unknown').substring(0, 8);
    const statusStr = meta.status || 'Success';
    const statusColor = statusStr === 'Failed' ? 'var(--severity-critical)' : 'var(--status-resolved)';

    // Compute consistent severity breakdown matching total findings
    let critCount = 0, highCount = 0, medCount = 0, lowCount = 0, infoCount = 0, closedCount = 0;
    currentRunVulns.forEach(v => {
      const st = String(v.status || "Open").toLowerCase();
      if (st === "closed") {
        closedCount++;
        return;
      }
      const sev = String(v.severity || "LOW").toUpperCase();
      if (sev === "CRITICAL") critCount++;
      else if (sev === "HIGH") highCount++;
      else if (sev === "MEDIUM") medCount++;
      else if (sev === "LOW") lowCount++;
      else infoCount++;
    });

    const totalVulns = currentRunVulns.length;
    const prLinkHtml = meta.pr
      ? `<div class="run-meta-item">PR: ${meta.pr.startsWith("http") ? `<a href="${meta.pr}" target="_blank" rel="noopener noreferrer" class="pr-link">${meta.pr}</a>` : `<strong>${meta.pr}</strong>`}</div>`
      : "";

    const triggerHtml = renderTriggerBadge(meta.trigger);
    const triggerMetaItem = triggerHtml
      ? `<div class="run-meta-item">Trigger: ${triggerHtml}</div>`
      : "";

    container.innerHTML = `
      <div class="run-meta-grid">
        ${prLinkHtml}
        <div class="run-meta-item">Project: <strong>${proj}</strong></div>
        ${triggerMetaItem}
        <div class="run-meta-item">Job: <strong>${job}</strong></div>
        <div class="run-meta-item">Model: <strong>${meta.model || 'Unknown'}</strong></div>
        <div class="run-meta-item">Commit: <code>${shortCommit}</code></div>
        <div class="run-meta-item">Mode: <strong>${meta.mode || 'Discovery'}</strong></div>
        <div class="run-meta-item">Status: <strong style="color: ${statusColor};">${statusStr}</strong></div>
        <div class="run-meta-item">Scan Time: <strong title="UTC: ${meta.timestamp || 'N/A'}">${formatLocalTimestamp(meta.timestamp)}</strong></div>
      </div>

      ${errorsHtml}

      <div class="metrics-grid">
        <div class="metric-card">
          <span class="metric-label">Total Findings</span>
          <span class="metric-value">${totalVulns}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Critical</span>
          <span class="metric-value" style="color: var(--severity-critical);">${critCount}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">High</span>
          <span class="metric-value" style="color: var(--severity-high);">${highCount}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Medium</span>
          <span class="metric-value" style="color: var(--severity-medium);">${medCount}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Low</span>
          <span class="metric-value" style="color: var(--severity-low);">${lowCount}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Info</span>
          <span class="metric-value" style="color: var(--severity-info);">${infoCount}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">Closed</span>
          <span class="metric-value" style="color: var(--text-muted);">${closedCount}</span>
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
        <button id="btn-export-csv" class="btn btn-secondary">Export CSV</button>
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
      </div>

      ${tokenUsageHtml}

      ${toolUsageHtml}`;

    workerComputeRunSankeyFlow(vulnsJson).then(runFlowJson => {
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
      const filteredRaw = await workerFilterVulnerabilities(vulnsJson, query, severity, status, sortOrder);
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

    document.getElementById("btn-export-csv").addEventListener("click", () => {
      const vulns = window.currentFiltered || currentRunVulns;
      const csvContent = generate_report(proj, job, runId, JSON.stringify(vulns), JSON.stringify(meta), "csv");
      downloadFile(`${proj}_${job}_${runId}_findings.csv`, csvContent, "text/csv");
    });

    document.getElementById("btn-export-md").addEventListener("click", () => {
      const vulns = window.currentFiltered || currentRunVulns;
      const mdContent = generate_report(proj, job, runId, JSON.stringify(vulns), JSON.stringify(meta), "markdown");
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

    await updateTable();

    // Auto open modal if deep linked to finding index
    if (deepLinkFindingIdx !== null && !isNaN(deepLinkFindingIdx) && window.currentFiltered?.[deepLinkFindingIdx]) {
      window.showFindingModal(deepLinkFindingIdx);
    }

  } catch (err) {
    container.innerHTML = renderEmptyState(
      "Failed to Load Run",
      err.message || "Could not retrieve run findings."
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
      const u = String(nodeName || '').toUpperCase();
      if (u.includes('CRITICAL')) return '#ef4444';
      if (u.includes('HIGH')) return '#f97316';
      if (u.includes('MEDIUM')) return '#eab308';
      if (u.includes('LOW')) return '#3b82f6';
      if (u.includes('INFO')) return '#38bdf8';
      if (u.includes('CLOSED')) return '#71717a';
      if (u.includes('SKIPPED')) return '#a1a1aa';
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
