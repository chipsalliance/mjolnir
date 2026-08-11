// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

window._toolStatsRegistry = window._toolStatsRegistry || {};

window.showToolRunsModal = function(encodedToolName) {
  const toolName = decodeURIComponent(encodedToolName);
  const item = window._toolStatsRegistry && window._toolStatsRegistry[toolName];
  if (!item) return;

  const rows = (item.runs || []).map(r => `
    <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'; if (window.closeModal) window.closeModal();">
      <td><strong>${r.project}</strong></td>
      <td>${r.job}</td>
      <td><code>${r.run_id}</code></td>
      <td>${r.calls}</td>
      <td style="color: var(--status-resolved);">${r.successes}</td>
      <td style="color: ${r.failures > 0 ? 'var(--severity-critical)' : 'inherit'};">${r.failures}</td>
      <td><span class="badge ${r.failures > 0 ? 'badge-critical' : 'badge-low'}">${r.failure_rate}</span></td>
      <td>${r.timestamp || "N/A"}</td>
    </tr>
  `).join("");

  const bodyHtml = `
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px;">
      <span class="badge" style="background-color: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border);">${item.runs.length} Associated Runs</span>
      <code>${toolName}</code>
    </div>
    <div class="table-container" style="max-height: 420px; overflow-y: auto; margin-bottom: 0;">
      <table>
        <thead>
          <tr>
            <th>Project</th>
            <th>Job Target</th>
            <th>Run Directory</th>
            <th>Calls</th>
            <th>Successes</th>
            <th>Failures</th>
            <th>Failure Rate</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          ${rows || '<tr><td colspan="8" style="text-align:center; padding: 20px;">No runs found.</td></tr>'}
        </tbody>
      </table>
    </div>
  `;

  if (typeof window.openModal === "function") {
    window.openModal(`Tool Usage: ${toolName}`, bodyHtml);
  }
};

export function extractRunToolStats(r) {
  const tu = r.tool_usage || {};
  const tot = tu.total || {};
  const totalCalls = tot.total_calls || 0;
  const totalSuccesses = tot.total_successes || 0;
  const totalFailures = tot.total_failures || 0;
  const failureRate = tot.failure_rate || (totalCalls > 0 ? `${((totalFailures / totalCalls) * 100).toFixed(2)}%` : "0.00%");

  return { totalCalls, totalSuccesses, totalFailures, failureRate, tu };
}

function aggregateRunsToolStats(runs) {
  let totalCalls = 0;
  let totalSuccesses = 0;
  let totalFailures = 0;
  const toolStats = {};
  const runRows = [];

  (runs || []).forEach((r) => {
    const { totalCalls: calls, totalSuccesses: succ, totalFailures: fail, failureRate: rate, tu } = extractRunToolStats(r);
    totalCalls += calls;
    totalSuccesses += succ;
    totalFailures += fail;

    if (tu.by_tool) {
      Object.entries(tu.by_tool).forEach(([tName, s]) => {
        if (!toolStats[tName]) {
          toolStats[tName] = { calls: 0, successes: 0, failures: 0, runs: [] };
        }
        const c = s.calls || 0;
        const sc = s.successes || 0;
        const fl = s.failures || 0;
        const fr = s.failure_rate || (c > 0 ? `${((fl / c) * 100).toFixed(2)}%` : "0.00%");

        toolStats[tName].calls += c;
        toolStats[tName].successes += sc;
        toolStats[tName].failures += fl;
        toolStats[tName].runs.push({
          project: r.project,
          job: r.job,
          run_id: r.run_id,
          calls: c,
          successes: sc,
          failures: fl,
          failure_rate: fr,
          timestamp: r.timestamp || "N/A",
        });
      });
    }

    if (calls > 0) {
      runRows.push(`
        <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'">
          <td><strong>${r.project}</strong></td>
          <td>${r.job}</td>
          <td><code>${r.run_id}</code></td>
          <td>${calls}</td>
          <td style="color: var(--status-resolved);">${succ}</td>
          <td style="color: ${fail > 0 ? 'var(--severity-critical)' : 'inherit'};">${fail}</td>
          <td><span class="badge ${fail > 0 ? 'badge-critical' : 'badge-low'}">${rate}</span></td>
        </tr>
      `);
    }
  });

  // Update global registry for modal lookups
  Object.assign(window._toolStatsRegistry, toolStats);

  return { totalCalls, totalSuccesses, totalFailures, toolStats, runRows };
}

function renderCollapsibleToolCard(totalCalls, totalSuccesses, totalFailures, tableRows, hasAssociatedRunsCol) {
  if (totalCalls === 0 && (!tableRows || tableRows.length === 0)) {
    return "";
  }

  const overallFailureRate = totalCalls > 0 ? `${((totalFailures / totalCalls) * 100).toFixed(2)}%` : "0.00%";
  const thExtra = hasAssociatedRunsCol ? `<th>Associated Runs</th>` : "";

  return `
    <details class="card" style="margin-top: 20px;">
      <summary class="card-title" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; user-select: none;">
        <span>Tool Usage (Click to Expand)</span>
        <span style="font-size: 13px; font-weight: normal;">Total Calls: <strong>${totalCalls.toLocaleString()}</strong> | Failure Rate: <strong>${overallFailureRate}</strong></span>
      </summary>
      <div style="margin-top: 15px;">
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
        <div class="table-container" style="margin-bottom: 0;">
          <table>
            <thead>
              <tr>
                <th>Tool Name</th>
                <th>Total Calls</th>
                <th>Successes</th>
                <th>Failures</th>
                <th>Failure Rate</th>
                ${thExtra}
              </tr>
            </thead>
            <tbody>
              ${tableRows}
            </tbody>
          </table>
        </div>
      </div>
    </details>`;
}

export function registerToolUsageModule(navContainer, routeHandlers, renderEmptyState, getRuns) {
  const container = navContainer || document.querySelector(".sidebar-nav");
  if (container) {
    const toolUsageLink = document.createElement("a");
    toolUsageLink.href = "#/tool-usage";
    toolUsageLink.className = "nav-item";
    toolUsageLink.id = "nav-tool-usage";
    toolUsageLink.innerHTML = "<span>Tool Usage</span>";

    const tokenUsageLink = document.getElementById("nav-token-usage");
    const allRunsLink = document.getElementById("nav-all-runs");
    if (tokenUsageLink && tokenUsageLink.parentNode) {
      tokenUsageLink.parentNode.insertBefore(toolUsageLink, tokenUsageLink.nextSibling);
    } else if (allRunsLink && allRunsLink.parentNode) {
      allRunsLink.parentNode.insertBefore(toolUsageLink, allRunsLink.nextSibling);
    } else {
      container.appendChild(toolUsageLink);
    }
  }

  if (routeHandlers) {
    routeHandlers["#/tool-usage"] = async (viewport) => {
      const runs = (typeof getRuns === "function" ? getRuns() : []) || [];
      const { totalCalls, totalSuccesses, totalFailures, toolStats, runRows } = aggregateRunsToolStats(runs);

      if (runs.length === 0 || totalCalls === 0) {
        if (renderEmptyState) {
          viewport.innerHTML = renderEmptyState(
            "No Tool Usage Recorded",
            "Run an analysis benchmark with tool execution to view tool usage metrics."
          );
        } else {
          viewport.innerHTML = `<div class="empty-state"><h3>No Tool Usage Recorded</h3><p>Run an analysis benchmark to record tool usage.</p></div>`;
        }
        return;
      }

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
            <td>
              <button class="badge-btn" onclick="window.showToolRunsModal('${encodeURIComponent(tName)}')">${s.runs.length} Runs</button>
            </td>
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
          <div class="card-title">Tool Usage Breakdown by Tool</div>
          <div class="table-container" style="margin-bottom: 0;">
            <table>
              <thead>
                <tr>
                  <th>Tool Name</th>
                  <th>Total Calls</th>
                  <th>Successes</th>
                  <th>Failures</th>
                  <th>Failure Rate</th>
                  <th>Associated Runs</th>
                </tr>
              </thead>
              <tbody>
                ${byToolRows || '<tr><td colspan="6" style="text-align:center; padding: 20px;">No tool executions recorded.</td></tr>'}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Tool Usage per Analysis Run</div>
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
                ${runRows.join("") || '<tr><td colspan="7" style="text-align:center; padding: 20px;">No runs recorded.</td></tr>'}
              </tbody>
            </table>
          </div>
        </div>`;
    };
  }
}

export function renderOverviewToolUsage(runs) {
  const { totalCalls, totalSuccesses, totalFailures, toolStats } = aggregateRunsToolStats(runs);
  const rows = Object.entries(toolStats).map(([tName, s]) => {
    const rate = s.calls > 0 ? `${((s.failures / s.calls) * 100).toFixed(2)}%` : "0.00%";
    return `
      <tr>
        <td><code>${tName}</code></td>
        <td>${s.calls}</td>
        <td style="color: var(--status-resolved);">${s.successes}</td>
        <td style="color: ${s.failures > 0 ? 'var(--severity-critical)' : 'inherit'};">${s.failures}</td>
        <td><span class="badge ${s.failures > 0 ? 'badge-critical' : 'badge-low'}">${rate}</span></td>
        <td>
          <button class="badge-btn" onclick="window.showToolRunsModal('${encodeURIComponent(tName)}')">${s.runs.length} Runs</button>
        </td>
      </tr>
    `;
  }).join("");
  return renderCollapsibleToolCard(totalCalls, totalSuccesses, totalFailures, rows, true);
}

export function renderProjectToolUsage(projRuns) {
  const { totalCalls, totalSuccesses, totalFailures, toolStats } = aggregateRunsToolStats(projRuns);
  const rows = Object.entries(toolStats).map(([tName, s]) => {
    const rate = s.calls > 0 ? `${((s.failures / s.calls) * 100).toFixed(2)}%` : "0.00%";
    return `
      <tr>
        <td><code>${tName}</code></td>
        <td>${s.calls}</td>
        <td style="color: var(--status-resolved);">${s.successes}</td>
        <td style="color: ${s.failures > 0 ? 'var(--severity-critical)' : 'inherit'};">${s.failures}</td>
        <td><span class="badge ${s.failures > 0 ? 'badge-critical' : 'badge-low'}">${rate}</span></td>
        <td>
          <button class="badge-btn" onclick="window.showToolRunsModal('${encodeURIComponent(tName)}')">${s.runs.length} Runs</button>
        </td>
      </tr>
    `;
  }).join("");
  return renderCollapsibleToolCard(totalCalls, totalSuccesses, totalFailures, rows, true);
}

export function renderRunToolUsage(data) {
  const toolUsage = (data && data.tool_usage) || {};
  const tot = toolUsage.total || {};
  const totalCalls = tot.total_calls || 0;
  const totalSuccesses = tot.total_successes || 0;
  const totalFailures = tot.total_failures || 0;
  const byTool = toolUsage.by_tool || {};

  const rows = Object.entries(byTool).map(([toolName, stats]) => `
    <tr>
      <td><code>${toolName}</code></td>
      <td>${stats.calls}</td>
      <td style="color: var(--status-resolved);">${stats.successes}</td>
      <td style="color: ${stats.failures > 0 ? 'var(--severity-critical)' : 'inherit'};">${stats.failures}</td>
      <td><span class="badge ${stats.failures > 0 ? 'badge-critical' : 'badge-low'}">${stats.failure_rate || '0.00%'}</span></td>
    </tr>
  `).join("");

  return renderCollapsibleToolCard(totalCalls, totalSuccesses, totalFailures, rows, false);
}
