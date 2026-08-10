// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

export function registerTokenUsageModule(navContainer, routeHandlers, renderEmptyState) {
  const container = navContainer || document.querySelector(".sidebar-nav");
  if (container) {
    const usageLink = document.createElement("a");
    usageLink.href = "#/token-usage";
    usageLink.className = "nav-item";
    usageLink.id = "nav-token-usage";
    usageLink.innerHTML = "<span>Token Usage</span>";

    const allRunsLink = document.getElementById("nav-all-runs");
    if (allRunsLink && allRunsLink.parentNode) {
      allRunsLink.parentNode.insertBefore(usageLink, allRunsLink.nextSibling);
    } else {
      container.appendChild(usageLink);
    }
  }

  routeHandlers["#/token-usage"] = async (viewport) => {
    viewport.innerHTML = `
      <div class="empty-state">
        <h3>Fetching Token Telemetry</h3>
        <p>Aggregating token usage metrics...</p>
      </div>`;

    try {
      let endpoint = "api/usage";
      let base = window.location.pathname;
      if (!base.endsWith("/") && !base.endsWith(".html")) {
        base += "/";
      }
      const fullUrl = new URL(endpoint, window.location.origin + base).href;
      const res = await fetch(fullUrl);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const usageData = await res.json();

      const byModelRows = (usageData.by_model || [])
        .map(
          (m) => `
        <tr>
          <td><strong>${m.model || "Unknown"}</strong></td>
          <td>${(m.input_tokens ?? m.prompt_tokens ?? 0).toLocaleString()}</td>
          <td>${(m.output_tokens ?? m.completion_tokens ?? 0).toLocaleString()}</td>
          <td><strong>${(m.total_tokens || 0).toLocaleString()}</strong></td>
          <td><span class="badge" style="background-color: var(--bg-card);">${m.runs_count || 0} Runs</span></td>
        </tr>
      `
        )
        .join("");

      const runsRows = (usageData.runs || [])
        .map(
          (r) => `
        <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'">
          <td><strong>${r.project}</strong></td>
          <td>${r.job}</td>
          <td><code>${r.run_id}</code></td>
          <td>${r.model || "N/A"}</td>
          <td><strong>${(r.total_tokens || 0).toLocaleString()}</strong></td>
          <td>${r.timestamp || "N/A"}</td>
        </tr>
      `
        )
        .join("");

      viewport.innerHTML = `
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label">Input Tokens</span>
            <span class="metric-value">${(usageData.total_input_tokens ?? usageData.total_prompt_tokens ?? 0).toLocaleString()}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Output Tokens</span>
            <span class="metric-value">${(usageData.total_output_tokens ?? usageData.total_completion_tokens ?? 0).toLocaleString()}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Total Tokens</span>
            <span class="metric-value" style="color: var(--accent);">${(usageData.total_tokens || 0).toLocaleString()}</span>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Token Usage Breakdown by AI Model</div>
          <div class="table-container" style="margin-bottom: 0;">
            <table>
              <thead>
                <tr>
                  <th>Model Name</th>
                  <th>Input Tokens</th>
                  <th>Output Tokens</th>
                  <th>Total Tokens</th>
                  <th>Associated Runs</th>
                </tr>
              </thead>
              <tbody>
                ${byModelRows || '<tr><td colspan="5" style="text-align:center; padding: 20px;">No usage data recorded yet.</td></tr>'}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Token Usage per Analysis Run</div>
          <div class="table-container" style="margin-bottom: 0;">
            <table>
              <thead>
                <tr>
                  <th>Project</th>
                  <th>Job Target</th>
                  <th>Run Directory</th>
                  <th>Model</th>
                  <th>Total Tokens</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                ${runsRows || '<tr><td colspan="6" style="text-align:center; padding: 20px;">No runs recorded.</td></tr>'}
              </tbody>
            </table>
          </div>
        </div>`;
    } catch (err) {
      viewport.innerHTML = renderEmptyState(
        "Usage Telemetry Unavailable",
        err.message || "Failed to load usage data."
      );
    }
  };
}

export function renderRunTokenUsage(data) {
  const tokenUsage = (data && data.token_usage) || {};
  if (!tokenUsage.by_model || Object.keys(tokenUsage.by_model).length === 0) {
    return "";
  }
  const tot = tokenUsage.total || {};
  const tokenRows = Object.entries(tokenUsage.by_model).map(([modelName, stats]) => `
    <tr>
      <td><code>${modelName}</code></td>
      <td>${(stats.input_tokens || 0).toLocaleString()}</td>
      <td>${(stats.output_tokens || 0).toLocaleString()}</td>
      <td><strong>${(stats.total_tokens || 0).toLocaleString()}</strong></td>
    </tr>
  `).join("");

  return `
    <details class="card" style="margin-bottom: 20px;">
      <summary class="card-title" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; user-select: none;">
        <span>Token Usage Telemetry (Click to Expand)</span>
        <span style="font-size: 13px; font-weight: normal;">Total Tokens: <strong>${(tot.total_tokens || 0).toLocaleString()}</strong></span>
      </summary>
      <div style="margin-top: 15px;">
        <table class="findings-table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Input Tokens</th>
              <th>Output Tokens</th>
              <th>Total Tokens</th>
            </tr>
          </thead>
          <tbody>
            ${tokenRows}
          </tbody>
        </table>
      </div>
    </details>`;
}
