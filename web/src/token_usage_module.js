// Licensed under the Apache-2.0 license
// SPDX-License-Identifier: Apache-2.0

window._tokenStatsRegistry = window._tokenStatsRegistry || {};

window.showTokenRunsModal = function(encodedKey) {
  const key = decodeURIComponent(encodedKey);
  const item = window._tokenStatsRegistry && window._tokenStatsRegistry[key];
  if (!item) return;

  const rows = (item.runs || []).map(r => `
    <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'; if (window.closeModal) window.closeModal();">
      <td><strong>${r.project}</strong></td>
      <td>${r.job}</td>
      <td><code>${r.run_id}</code></td>
      <td>${(r.input_tokens || 0).toLocaleString()}</td>
      <td>${(r.output_tokens || 0).toLocaleString()}</td>
      <td><strong>${(r.total_tokens || 0).toLocaleString()}</strong></td>
      <td>${r.timestamp || "N/A"}</td>
    </tr>
  `).join("");

  const bodyHtml = `
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 16px;">
      <span class="badge" style="background-color: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border);">${item.runs.length} Associated Runs</span>
      <code>${item.agent ? item.agent + ' (' + item.model + ')' : item.model}</code>
    </div>
    <div class="table-container" style="max-height: 420px; overflow-y: auto; margin-bottom: 0;">
      <table>
        <thead>
          <tr>
            <th>Project</th>
            <th>Job Target</th>
            <th>Run Directory</th>
            <th>Input Tokens</th>
            <th>Output Tokens</th>
            <th>Total Tokens</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          ${rows || '<tr><td colspan="7" style="text-align:center; padding: 20px;">No runs found.</td></tr>'}
        </tbody>
      </table>
    </div>
  `;

  if (typeof window.openModal === "function") {
    window.openModal(`Token Usage: ${item.agent ? item.agent + ' (' + item.model + ')' : item.model}`, bodyHtml);
  }
};

export function extractRunTokenStats(r) {
  const tu = r.token_usage || {};
  const tot = tu.total || {};
  const prompt = tot.total_input_tokens ?? tot.prompt_tokens ?? 0;
  const comp = tot.total_output_tokens ?? tot.output_tokens ?? tot.completion_tokens ?? 0;
  const total = tot.total_tokens ?? (prompt + comp);

  let modelName = r.model || "Unknown";
  if (tu.by_agent) {
    const agents = Object.values(tu.by_agent);
    if (agents.length > 0 && agents[0].model) {
      modelName = agents[0].model;
    }
  } else if (tu.by_model) {
    const models = Object.keys(tu.by_model);
    if (models.length > 0) {
      modelName = models[0];
    }
  }

  return { prompt, comp, total, modelName, tu };
}

function aggregateRunsTokenStats(runs) {
  let totalInput = 0;
  let totalOutput = 0;
  let totalTokens = 0;
  const agentModelStats = {};
  const runRows = [];

  (runs || []).forEach((r) => {
    const { prompt, comp, total, modelName, tu } = extractRunTokenStats(r);
    totalInput += prompt;
    totalOutput += comp;
    totalTokens += total;

    if (tu.by_agent && Object.keys(tu.by_agent).length > 0) {
      Object.entries(tu.by_agent).forEach(([agentName, st]) => {
        const mName = st.model || modelName || "Unknown";
        const key = `${agentName} (${mName})`;
        if (!agentModelStats[key]) {
          agentModelStats[key] = {
            key,
            agent: agentName,
            model: mName,
            input_tokens: 0,
            output_tokens: 0,
            total_tokens: 0,
            runs: [],
          };
        }
        const inp = st.total_input_tokens ?? st.prompt_tokens ?? 0;
        const out = st.total_output_tokens ?? st.output_tokens ?? 0;
        const tok = st.total_tokens ?? (inp + out);
        agentModelStats[key].input_tokens += inp;
        agentModelStats[key].output_tokens += out;
        agentModelStats[key].total_tokens += tok;
        agentModelStats[key].runs.push({
          project: r.project,
          job: r.job,
          run_id: r.run_id,
          model: mName,
          agent: agentName,
          input_tokens: inp,
          output_tokens: out,
          total_tokens: tok,
          timestamp: r.timestamp || "N/A",
        });
      });
    } else if (tu.by_model && Object.keys(tu.by_model).length > 0) {
      Object.entries(tu.by_model).forEach(([mName, st]) => {
        const key = mName;
        if (!agentModelStats[key]) {
          agentModelStats[key] = {
            key,
            agent: "Default",
            model: mName,
            input_tokens: 0,
            output_tokens: 0,
            total_tokens: 0,
            runs: [],
          };
        }
        const inp = st.input_tokens ?? st.prompt_tokens ?? 0;
        const out = st.output_tokens ?? st.completion_tokens ?? 0;
        const tok = st.total_tokens ?? (inp + out);
        agentModelStats[key].input_tokens += inp;
        agentModelStats[key].output_tokens += out;
        agentModelStats[key].total_tokens += tok;
        agentModelStats[key].runs.push({
          project: r.project,
          job: r.job,
          run_id: r.run_id,
          model: mName,
          agent: "Default",
          input_tokens: inp,
          output_tokens: out,
          total_tokens: tok,
          timestamp: r.timestamp || "N/A",
        });
      });
    } else if (total > 0) {
      const key = modelName;
      if (!agentModelStats[key]) {
        agentModelStats[key] = {
          key,
          agent: "Default",
          model: modelName,
          input_tokens: 0,
          output_tokens: 0,
          total_tokens: 0,
          runs: [],
        };
      }
      agentModelStats[key].input_tokens += prompt;
      agentModelStats[key].output_tokens += comp;
      agentModelStats[key].total_tokens += total;
      agentModelStats[key].runs.push({
        project: r.project,
        job: r.job,
        run_id: r.run_id,
        model: modelName,
        agent: "Default",
        input_tokens: prompt,
        output_tokens: comp,
        total_tokens: total,
        timestamp: r.timestamp || "N/A",
      });
    }

    if (total > 0) {
      runRows.push(`
        <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'">
          <td><strong>${r.project}</strong></td>
          <td>${r.job}</td>
          <td><code>${r.run_id}</code></td>
          <td>${modelName}</td>
          <td><strong>${total.toLocaleString()}</strong></td>
          <td>${r.timestamp || "N/A"}</td>
        </tr>
      `);
    }
  });

  // Update global registry for modal lookups
  Object.assign(window._tokenStatsRegistry, agentModelStats);

  return { totalInput, totalOutput, totalTokens, agentModelStats, runRows };
}

function renderCollapsibleTokenCard(totalInput, totalOutput, totalTokens, tableRows, hasAssociatedRunsCol) {
  if (totalTokens === 0 && (!tableRows || tableRows.length === 0)) {
    return "";
  }

  const thExtra = hasAssociatedRunsCol ? `<th>Associated Runs</th>` : "";

  return `
    <details class="card" style="margin-top: 20px;">
      <summary class="card-title" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; user-select: none;">
        <span>Token Usage (Click to Expand)</span>
        <span style="font-size: 13px; font-weight: normal;">Total Tokens: <strong>${totalTokens.toLocaleString()}</strong></span>
      </summary>
      <div style="margin-top: 15px;">
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label">Input Tokens</span>
            <span class="metric-value">${totalInput.toLocaleString()}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Output Tokens</span>
            <span class="metric-value">${totalOutput.toLocaleString()}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Total Tokens</span>
            <span class="metric-value" style="color: var(--accent);">${totalTokens.toLocaleString()}</span>
          </div>
        </div>
        <div class="table-container" style="margin-bottom: 0;">
          <table>
            <thead>
              <tr>
                <th>Agent / Model</th>
                <th>Input Tokens</th>
                <th>Output Tokens</th>
                <th>Total Tokens</th>
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

export function registerTokenUsageModule(navContainer, routeHandlers, renderEmptyState, getRuns) {
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

  if (routeHandlers) {
    routeHandlers["#/token-usage"] = async (viewport) => {
      const runs = (typeof getRuns === "function" ? getRuns() : []) || [];
      const { totalInput, totalOutput, totalTokens, agentModelStats, runRows } = aggregateRunsTokenStats(runs);

      if (runs.length === 0 || totalTokens === 0) {
        if (renderEmptyState) {
          viewport.innerHTML = renderEmptyState(
            "No Token Usage Recorded",
            "Run an analysis benchmark with AI model execution to view token usage."
          );
        } else {
          viewport.innerHTML = `<div class="empty-state"><h3>No Token Usage Recorded</h3><p>Run an analysis benchmark to record token usage.</p></div>`;
        }
        return;
      }

      const byModelRows = Object.values(agentModelStats).map((m) => `
        <tr>
          <td><strong>${m.agent}</strong> (<code>${m.model}</code>)</td>
          <td>${(m.input_tokens || 0).toLocaleString()}</td>
          <td>${(m.output_tokens || 0).toLocaleString()}</td>
          <td><strong>${(m.total_tokens || 0).toLocaleString()}</strong></td>
          <td>
            <button class="badge-btn" onclick="window.showTokenRunsModal('${encodeURIComponent(m.key)}')">${m.runs.length} Runs</button>
          </td>
        </tr>
      `).join("");

      viewport.innerHTML = `
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label">Input Tokens</span>
            <span class="metric-value">${totalInput.toLocaleString()}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Output Tokens</span>
            <span class="metric-value">${totalOutput.toLocaleString()}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Total Tokens</span>
            <span class="metric-value" style="color: var(--accent);">${totalTokens.toLocaleString()}</span>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Token Usage Breakdown by AI Agent / Model</div>
          <div class="table-container" style="margin-bottom: 0;">
            <table>
              <thead>
                <tr>
                  <th>Agent / Model</th>
                  <th>Input Tokens</th>
                  <th>Output Tokens</th>
                  <th>Total Tokens</th>
                  <th>Associated Runs</th>
                </tr>
              </thead>
              <tbody>
                ${byModelRows || '<tr><td colspan="5" style="text-align:center; padding: 20px;">No token usage data recorded yet.</td></tr>'}
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
                ${runRows.join("") || '<tr><td colspan="6" style="text-align:center; padding: 20px;">No runs recorded.</td></tr>'}
              </tbody>
            </table>
          </div>
        </div>`;
    };
  }
}

export function renderOverviewTokenUsage(runs) {
  const { totalInput, totalOutput, totalTokens, agentModelStats } = aggregateRunsTokenStats(runs);
  const rows = Object.values(agentModelStats).map((m) => `
    <tr>
      <td><strong>${m.agent}</strong> (<code>${m.model}</code>)</td>
      <td>${(m.input_tokens || 0).toLocaleString()}</td>
      <td>${(m.output_tokens || 0).toLocaleString()}</td>
      <td><strong>${(m.total_tokens || 0).toLocaleString()}</strong></td>
      <td>
        <button class="badge-btn" onclick="window.showTokenRunsModal('${encodeURIComponent(m.key)}')">${m.runs.length} Runs</button>
      </td>
    </tr>
  `).join("");
  return renderCollapsibleTokenCard(totalInput, totalOutput, totalTokens, rows, true);
}

export function renderProjectTokenUsage(projRuns) {
  const { totalInput, totalOutput, totalTokens, agentModelStats } = aggregateRunsTokenStats(projRuns);
  const rows = Object.values(agentModelStats).map((m) => `
    <tr>
      <td><strong>${m.agent}</strong> (<code>${m.model}</code>)</td>
      <td>${(m.input_tokens || 0).toLocaleString()}</td>
      <td>${(m.output_tokens || 0).toLocaleString()}</td>
      <td><strong>${(m.total_tokens || 0).toLocaleString()}</strong></td>
      <td>
        <button class="badge-btn" onclick="window.showTokenRunsModal('${encodeURIComponent(m.key)}')">${m.runs.length} Runs</button>
      </td>
    </tr>
  `).join("");
  return renderCollapsibleTokenCard(totalInput, totalOutput, totalTokens, rows, true);
}

export function renderRunTokenUsage(data) {
  const tokenUsage = (data && data.token_usage) || {};
  const tot = tokenUsage.total || {};
  const prompt = tot.total_input_tokens ?? tot.prompt_tokens ?? 0;
  const comp = tot.total_output_tokens ?? tot.output_tokens ?? tot.completion_tokens ?? 0;
  const totalTokens = tot.total_tokens ?? (prompt + comp);
  const byAgent = tokenUsage.by_agent || {};
  const byModel = tokenUsage.by_model || {};

  const rows = [];
  if (Object.keys(byAgent).length > 0) {
    Object.entries(byAgent).forEach(([agentName, stats]) => {
      const inp = stats.total_input_tokens ?? stats.prompt_tokens ?? 0;
      const out = stats.total_output_tokens ?? stats.output_tokens ?? 0;
      const tok = stats.total_tokens ?? (inp + out);
      rows.push(`
        <tr>
          <td><strong>${agentName}</strong> (<code>${stats.model || "Unknown"}</code>)</td>
          <td>${inp.toLocaleString()}</td>
          <td>${out.toLocaleString()}</td>
          <td><strong>${tok.toLocaleString()}</strong></td>
        </tr>
      `);
    });
  } else if (Object.keys(byModel).length > 0) {
    Object.entries(byModel).forEach(([modelName, stats]) => {
      const inp = stats.input_tokens ?? stats.prompt_tokens ?? 0;
      const out = stats.output_tokens ?? stats.completion_tokens ?? 0;
      const tok = stats.total_tokens ?? (inp + out);
      rows.push(`
        <tr>
          <td><code>${modelName}</code></td>
          <td>${inp.toLocaleString()}</td>
          <td>${out.toLocaleString()}</td>
          <td><strong>${tok.toLocaleString()}</strong></td>
        </tr>
      `);
    });
  } else if (totalTokens > 0) {
    const modelName = (data && data.metadata && data.metadata.model) || "Default";
    rows.push(`
      <tr>
        <td><code>${modelName}</code></td>
        <td>${prompt.toLocaleString()}</td>
        <td>${comp.toLocaleString()}</td>
        <td><strong>${totalTokens.toLocaleString()}</strong></td>
      </tr>
    `);
  }

  return renderCollapsibleTokenCard(prompt, comp, totalTokens, rows.join(""), false);
}
