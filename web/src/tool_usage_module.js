// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

export function registerToolUsageModule(navContainer, routeHandlers, renderEmptyState) {
  const container = navContainer || document.querySelector(".sidebar-nav");
  if (container) {
    const toolUsageLink = document.createElement("a");
    toolUsageLink.href = "#/tool-usage";
    toolUsageLink.className = "nav-item";
    toolUsageLink.id = "nav-tool-usage";
    toolUsageLink.innerHTML = "<span>Tool Usage</span>";

    const allRunsLink = document.getElementById("nav-all-runs");
    if (allRunsLink && allRunsLink.parentNode) {
      allRunsLink.parentNode.insertBefore(toolUsageLink, allRunsLink.nextSibling);
    } else {
      container.appendChild(toolUsageLink);
    }
  }

  if (routeHandlers) {
    routeHandlers["#/tool-usage"] = async (viewport) => {
      viewport.innerHTML = `
        <div class="empty-state">
          <h3>Fetching Tool Telemetry</h3>
          <p>Aggregating tool execution and failure rate metrics...</p>
        </div>`;

      try {
        let endpoint = "api/runs";
        let base = window.location.pathname;
        if (!base.endsWith("/") && !base.endsWith(".html")) {
          base += "/";
        }
        const fullUrl = new URL(endpoint, window.location.origin + base).href;
        const res = await fetch(fullUrl);
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        const runs = await res.json();

        let totalCalls = 0;
        let totalSuccesses = 0;
        let totalFailures = 0;
        const toolStats = {};
        const runRows = [];

        (runs || []).forEach((r) => {
          const tu = r.tool_usage || {};
          const tot = tu.total || {};
          totalCalls += tot.total_calls || 0;
          totalSuccesses += tot.total_successes || 0;
          totalFailures += tot.total_failures || 0;

          if (tu.by_tool) {
            Object.entries(tu.by_tool).forEach(([tName, s]) => {
              if (!toolStats[tName]) {
                toolStats[tName] = { calls: 0, successes: 0, failures: 0 };
              }
              toolStats[tName].calls += s.calls || 0;
              toolStats[tName].successes += s.successes || 0;
              toolStats[tName].failures += s.failures || 0;
            });
          }

          if (tot.total_calls > 0) {
            runRows.push(`
              <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'">
                <td><strong>${r.project}</strong></td>
                <td>${r.job}</td>
                <td><code>${r.run_id}</code></td>
                <td>${tot.total_calls}</td>
                <td style="color: var(--status-resolved);">${tot.total_successes}</td>
                <td style="color: ${tot.total_failures > 0 ? 'var(--severity-critical)' : 'inherit'};">${tot.total_failures}</td>
                <td><span class="badge ${tot.total_failures > 0 ? 'badge-critical' : 'badge-low'}">${tot.failure_rate || '0.00%'}</span></td>
              </tr>
            `);
          }
        });

        const overallFailureRate = totalCalls > 0 ? `${((totalFailures / totalCalls) * 100).toFixed(2)}%` : "0.00%";

        const byToolRows = Object.entries(toolStats).map(([tName, s]) => {
          const rate = s.calls > 0 ? `${((s.failures / s.calls) * 100).toFixed(2)}%` : "0.00%";
          return `
            <tr>
              <td><code>${tName}</code></td>
              <td>${s.calls}</td>
              <td style="color: var(--status-resolved);">${s.successes}</td>
              <td style="color: ${s.failures > 0 ? 'var(--severity-critical)' : 'inherit'};">${s.failures}</td>
              <td><span class="badge ${s.failures > 0 ? 'badge-critical' : 'badge-low'}">${rate}</span></td>
            </tr>
          `;
        }).join("");

        viewport.innerHTML = `
          <div class="metrics-grid">
            <div class="metric-card">
              <span class="metric-label">Total Tool Calls</span>
              <span class="metric-value">${totalCalls.toLocaleString()}</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">Successful Execution</span>
              <span class="metric-value" style="color: var(--status-resolved);">${totalSuccesses.toLocaleString()}</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">Failed / Timed Out</span>
              <span class="metric-value" style="color: ${totalFailures > 0 ? 'var(--severity-critical)' : 'inherit'};">${totalFailures.toLocaleString()}</span>
            </div>
            <div class="metric-card">
              <span class="metric-label">Overall Failure Rate</span>
              <span class="metric-value" style="color: var(--accent);">${overallFailureRate}</span>
            </div>
          </div>

          <div class="card">
            <div class="card-title">Global Tool Performance Breakdown</div>
            <div class="table-container" style="margin-bottom: 0;">
              <table>
                <thead>
                  <tr>
                    <th>Tool Name</th>
                    <th>Total Calls</th>
                    <th>Successes</th>
                    <th>Failures</th>
                    <th>Failure Rate</th>
                  </tr>
                </thead>
                <tbody>
                  ${byToolRows || '<tr><td colspan="5" style="text-align:center; padding: 20px;">No tool executions recorded.</td></tr>'}
                </tbody>
              </table>
            </div>
          </div>

          <div class="card">
            <div class="card-title">Tool Execution per Analysis Run</div>
            <div class="table-container" style="margin-bottom: 0;">
              <table>
                <thead>
                  <tr>
                    <th>Project</th>
                    <th>Job Target</th>
                    <th>Run Directory</th>
                    <th>Tool Calls</th>
                    <th>Successes</th>
                    <th>Failures</th>
                    <th>Failure Rate</th>
                  </tr>
                </thead>
                <tbody>
                  ${runRows.join("") || '<tr><td colspan="7" style="text-align:center; padding: 20px;">No run telemetry recorded.</td></tr>'}
                </tbody>
              </table>
            </div>
          </div>`;
      } catch (err) {
        if (renderEmptyState) {
          viewport.innerHTML = renderEmptyState(
            "Tool Telemetry Unavailable",
            err.message || "Failed to load tool telemetry."
          );
        } else {
          viewport.innerHTML = `<div class="empty-state"><h3>Tool Telemetry Unavailable</h3><p>${err.message}</p></div>`;
        }
      }
    };
  }
}
