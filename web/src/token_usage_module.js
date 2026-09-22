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
      <td>${(r.uncached_tokens || 0).toLocaleString()}</td>
      <td>${(r.cache_tokens || 0).toLocaleString()}</td>
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
            <th>Uncached Input</th>
            <th>Cached Content</th>
            <th>Output Tokens</th>
            <th>Total Tokens</th>
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
    window.openModal(`Token Usage: ${item.agent ? item.agent + ' (' + item.model + ')' : item.model}`, bodyHtml);
  }
};

function countRefusalsFromGrouped(errorsGrouped) {
  let refusals = 0;
  Object.entries(errorsGrouped || {}).forEach(([errKey, count]) => {
    if (/refusal|safety|recitation|blocklist|prohibited/i.test(errKey)) {
      refusals += Number(count) || 0;
    }
  });
  return refusals;
}

function classifyErrorBadge(errKey) {
  if (/refusal|safety|recitation|blocklist|prohibited/i.test(errKey)) {
    return `<span class="badge" style="background-color: rgba(244, 63, 94, 0.15); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.3);">Model Refusal</span>`;
  }
  if (/schema|validation/i.test(errKey)) {
    return `<span class="badge" style="background-color: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3);">Schema Validation</span>`;
  }
  return `<span class="badge" style="background-color: rgba(148, 163, 184, 0.15); color: var(--text-secondary); border: 1px solid rgba(148, 163, 184, 0.3);">Runtime / API Error</span>`;
}

function renderGroupedErrorsTable(errorsGrouped) {
  const entries = Object.entries(errorsGrouped || {}).sort((a, b) => (Number(b[1]) || 0) - (Number(a[1]) || 0));
  if (entries.length === 0) {
    return "";
  }
  const rows = entries.map(([errKey, count]) => `
    <tr>
      <td>${classifyErrorBadge(errKey)}</td>
      <td><code>${String(errKey).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</code></td>
      <td><strong>${(Number(count) || 0).toLocaleString()}</strong></td>
    </tr>
  `).join("");

  return `
    <div style="margin-top: 16px;">
      <div style="font-size: 13px; font-weight: 600; margin-bottom: 8px; color: var(--text-primary);">Grouped Error & Refusal Breakdown</div>
      <div class="table-container" style="margin-bottom: 0;">
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th>Error / Refusal Signature</th>
              <th>Occurrences</th>
            </tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

export function extractRunTokenStats(r) {
  const tu = r.token_usage || {};
  const tot = tu.total || {};
  const prompt = tot.total_input_tokens ?? tot.prompt_tokens ?? 0;
  const uncached = tot.uncached_tokens ?? (prompt - (tot.cache_tokens || 0));
  const cached = tot.cache_tokens ?? 0;
  const comp = tot.output_tokens ?? tot.total_output_tokens ?? tot.completion_tokens ?? 0;
  const thoughts = tot.thoughts_tokens ?? 0;
  const total = tot.total_tokens ?? (prompt + comp + thoughts);
  const errors = tot.total_errors ?? tot.errors ?? 0;
  const errorsGrouped = tu.errors_grouped || {};
  const refusals = countRefusalsFromGrouped(errorsGrouped);
  const cacheHitRate = prompt > 0 && cached > 0 ? `${((cached / prompt) * 100).toFixed(1)}%` : "0.0%";

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

  return { prompt, uncached, cached, comp, thoughts, total, errors, refusals, errorsGrouped, cacheHitRate, modelName, tu };
}

function aggregateRunsTokenStats(runs) {
  let totalInput = 0;
  let totalUncached = 0;
  let totalCached = 0;
  let totalOutput = 0;
  let totalThoughts = 0;
  let totalTokens = 0;
  let totalErrors = 0;
  let totalRefusals = 0;
  const aggregatedErrorsGrouped = {};
  const agentModelStats = {};
  const runRows = [];

  (runs || []).forEach((r) => {
    const { prompt, uncached, cached, comp, thoughts, total, errors, refusals, errorsGrouped, cacheHitRate, modelName, tu } = extractRunTokenStats(r);
    totalInput += prompt;
    totalUncached += uncached;
    totalCached += cached;
    totalOutput += comp;
    totalThoughts += thoughts;
    totalTokens += total;
    totalErrors += errors;
    totalRefusals += refusals;

    Object.entries(errorsGrouped || {}).forEach(([errKey, cnt]) => {
      aggregatedErrorsGrouped[errKey] = (aggregatedErrorsGrouped[errKey] || 0) + (Number(cnt) || 0);
    });

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
            uncached_tokens: 0,
            cache_tokens: 0,
            output_tokens: 0,
            thoughts_tokens: 0,
            total_tokens: 0,
            errors: 0,
            runs: [],
          };
        }
        const inp = st.total_input_tokens ?? st.prompt_tokens ?? 0;
        const uncache = st.uncached_tokens ?? (inp - (st.cache_tokens || 0));
        const cache = st.cache_tokens ?? 0;
        const out = st.output_tokens ?? 0;
        const th = st.thoughts_tokens ?? 0;
        const tok = st.total_tokens ?? (inp + out + th);
        const errCount = st.errors ?? 0;

        agentModelStats[key].input_tokens += inp;
        agentModelStats[key].uncached_tokens += uncache;
        agentModelStats[key].cache_tokens += cache;
        agentModelStats[key].output_tokens += out;
        agentModelStats[key].thoughts_tokens += th;
        agentModelStats[key].total_tokens += tok;
        agentModelStats[key].errors += errCount;
        agentModelStats[key].runs.push({
          project: r.project,
          job: r.job,
          run_id: r.run_id,
          model: mName,
          agent: agentName,
          input_tokens: inp,
          uncached_tokens: uncache,
          cache_tokens: cache,
          output_tokens: out,
          thoughts_tokens: th,
          total_tokens: tok,
          errors: errCount,
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
          uncached_tokens: 0,
          cache_tokens: 0,
          output_tokens: 0,
          thoughts_tokens: 0,
          total_tokens: 0,
          errors: 0,
          runs: [],
        };
      }
      agentModelStats[key].input_tokens += prompt;
      agentModelStats[key].uncached_tokens += uncached;
      agentModelStats[key].cache_tokens += cached;
      agentModelStats[key].output_tokens += comp;
      agentModelStats[key].thoughts_tokens += thoughts;
      agentModelStats[key].total_tokens += total;
      agentModelStats[key].errors += errors;
      agentModelStats[key].runs.push({
        project: r.project,
        job: r.job,
        run_id: r.run_id,
        model: modelName,
        agent: "Default",
        input_tokens: prompt,
        uncached_tokens: uncached,
        cache_tokens: cached,
        output_tokens: comp,
        thoughts_tokens: thoughts,
        total_tokens: total,
        errors,
        timestamp: r.timestamp || "N/A",
      });
    }

    if (total > 0 || errors > 0) {
      const errBadge = errors > 0
        ? `<span class="badge" style="background-color: rgba(244, 63, 94, 0.15); color: #f43f5e;">${errors} (${refusals} refusals)</span>`
        : `<span class="badge" style="background-color: rgba(16, 185, 129, 0.15); color: #10b981;">0</span>`;
      runRows.push(`
        <tr class="clickable-row" onclick="window.location.hash='#/run/${r.project}/${r.job}/${r.run_id}'">
          <td><strong>${r.project}</strong></td>
          <td>${r.job}</td>
          <td><code>${r.run_id}</code></td>
          <td>${modelName}</td>
          <td>${(uncached || 0).toLocaleString()}</td>
          <td>${(cached || 0).toLocaleString()} <span class="badge badge-low" style="font-size:10px;">${cacheHitRate}</span></td>
          <td>${((comp || 0) + (thoughts || 0)).toLocaleString()}</td>
          <td><strong>${total.toLocaleString()}</strong></td>
          <td>${errBadge}</td>
          <td>${r.timestamp || "N/A"}</td>
        </tr>
      `);
    }
  });

  // Update global registry for modal lookups
  Object.assign(window._tokenStatsRegistry, agentModelStats);

  const overallCacheRate = totalInput > 0 && totalCached > 0 ? `${((totalCached / totalInput) * 100).toFixed(1)}%` : "0.0%";

  return { totalInput, totalUncached, totalCached, totalOutput, totalThoughts, totalTokens, totalErrors, totalRefusals, aggregatedErrorsGrouped, overallCacheRate, agentModelStats, runRows };
}

function renderCollapsibleTokenCard(totalInput, totalUncached, totalCached, totalOutput, totalThoughts, totalTokens, overallCacheRate, tableRows, hasAssociatedRunsCol, totalErrors = 0, totalRefusals = 0, errorsGrouped = {}) {
  if (totalTokens === 0 && totalErrors === 0 && (!tableRows || tableRows.length === 0)) {
    return "";
  }

  const thExtra = hasAssociatedRunsCol ? `<th>Associated Runs</th>` : "";
  const errSummaryBadge = totalErrors > 0
    ? ` &nbsp;|&nbsp; Errors/Refusals: <strong style="color: var(--severity-high);">${totalErrors.toLocaleString()} (${totalRefusals.toLocaleString()} refusals)</strong>`
    : ` &nbsp;|&nbsp; Errors/Refusals: <strong style="color: var(--status-resolved);">0</strong>`;

  return `
    <details class="card" style="margin-top: 20px;">
      <summary class="card-title" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; user-select: none;">
        <span>Token Usage & Error/Refusal Breakdown (Click to Expand)</span>
        <span style="font-size: 13px; font-weight: normal;">Total Tokens: <strong>${totalTokens.toLocaleString()}</strong>${errSummaryBadge}</span>
      </summary>
      <div style="margin-top: 15px;">
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label">Input Tokens (Prompt)</span>
            <span class="metric-value">${totalInput.toLocaleString()}</span>
            <span style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">${totalUncached.toLocaleString()} uncached / ${totalCached.toLocaleString()} cached</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Context Cache Hit Rate</span>
            <span class="metric-value" style="color: var(--status-resolved);">${overallCacheRate}</span>
            <span style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">${totalCached.toLocaleString()} tokens cached</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Output & Thinking</span>
            <span class="metric-value">${(totalOutput + totalThoughts).toLocaleString()}</span>
            <span style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">${totalThoughts.toLocaleString()} thoughts / ${totalOutput.toLocaleString()} output</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Total Tokens</span>
            <span class="metric-value" style="color: var(--accent);">${totalTokens.toLocaleString()}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Errors & Refusals</span>
            <span class="metric-value" style="color: ${totalErrors > 0 ? 'var(--severity-high)' : 'var(--status-resolved)'};">${totalErrors.toLocaleString()}</span>
            <span style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">${totalRefusals.toLocaleString()} refusals / ${Math.max(0, totalErrors - totalRefusals).toLocaleString()} runtime & schema</span>
          </div>
        </div>
        <div class="table-container" style="margin-bottom: 0;">
          <table>
            <thead>
              <tr>
                <th>Agent / Model</th>
                <th>Uncached Input</th>
                <th>Cached Content</th>
                <th>Thoughts</th>
                <th>Output Tokens</th>
                <th>Total Tokens</th>
                <th>Errors</th>
                ${thExtra}
              </tr>
            </thead>
            <tbody>
              ${tableRows}
            </tbody>
          </table>
        </div>
        ${renderGroupedErrorsTable(errorsGrouped)}
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
      const { totalInput, totalUncached, totalCached, totalOutput, totalThoughts, totalTokens, totalErrors, totalRefusals, aggregatedErrorsGrouped, overallCacheRate, agentModelStats, runRows } = aggregateRunsTokenStats(runs);

      if (runs.length === 0 || (totalTokens === 0 && totalErrors === 0)) {
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

      const byModelRows = Object.values(agentModelStats).map((m) => {
        const errVal = m.errors || 0;
        const errCell = errVal > 0
          ? `<strong style="color: var(--severity-high);">${errVal.toLocaleString()}</strong>`
          : `<span style="color: var(--status-resolved);">0</span>`;
        return `
        <tr>
          <td><strong>${m.agent}</strong> (<code>${m.model}</code>)</td>
          <td>${(m.uncached_tokens || 0).toLocaleString()}</td>
          <td>${(m.cache_tokens || 0).toLocaleString()}</td>
          <td>${(m.thoughts_tokens || 0).toLocaleString()}</td>
          <td>${(m.output_tokens || 0).toLocaleString()}</td>
          <td><strong>${(m.total_tokens || 0).toLocaleString()}</strong></td>
          <td>${errCell}</td>
          <td>
            <button class="badge-btn" onclick="window.showTokenRunsModal('${encodeURIComponent(m.key)}')">${m.runs.length} Runs</button>
          </td>
        </tr>
      `;
      }).join("");

      viewport.innerHTML = `
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label">Total Input Tokens</span>
            <span class="metric-value">${totalInput.toLocaleString()}</span>
            <span style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">${totalUncached.toLocaleString()} uncached / ${totalCached.toLocaleString()} cached</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Context Cache Hit Rate</span>
            <span class="metric-value" style="color: var(--status-resolved);">${overallCacheRate}</span>
            <span style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">${totalCached.toLocaleString()} tokens saved</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Output & Thinking</span>
            <span class="metric-value">${(totalOutput + totalThoughts).toLocaleString()}</span>
            <span style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">${totalThoughts.toLocaleString()} thoughts / ${totalOutput.toLocaleString()} output</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Total Tokens</span>
            <span class="metric-value" style="color: var(--accent);">${totalTokens.toLocaleString()}</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Errors & Refusals</span>
            <span class="metric-value" style="color: ${totalErrors > 0 ? 'var(--severity-high)' : 'var(--status-resolved)'};">${totalErrors.toLocaleString()}</span>
            <span style="font-size: 11px; color: var(--text-secondary); margin-top: 4px;">${totalRefusals.toLocaleString()} refusals / ${Math.max(0, totalErrors - totalRefusals).toLocaleString()} runtime & schema</span>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Token Usage Breakdown by AI Agent / Model</div>
          <div class="table-container" style="margin-bottom: 0;">
            <table>
              <thead>
                <tr>
                  <th>Agent / Model</th>
                  <th>Uncached Input</th>
                  <th>Cached Content</th>
                  <th>Thoughts</th>
                  <th>Output Tokens</th>
                  <th>Total Tokens</th>
                  <th>Errors</th>
                  <th>Associated Runs</th>
                </tr>
              </thead>
              <tbody>
                ${byModelRows || '<tr><td colspan="8" style="text-align:center; padding: 20px;">No token usage data recorded yet.</td></tr>'}
              </tbody>
            </table>
          </div>
          ${renderGroupedErrorsTable(aggregatedErrorsGrouped)}
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
                  <th>Uncached</th>
                  <th>Cached Content</th>
                  <th>Output</th>
                  <th>Total Tokens</th>
                  <th>Errors / Refusals</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                ${runRows.join("") || '<tr><td colspan="10" style="text-align:center; padding: 20px;">No runs recorded.</td></tr>'}
              </tbody>
            </table>
          </div>
        </div>`;
    };
  }
}

export function renderOverviewTokenUsage(runs) {
  const { totalInput, totalUncached, totalCached, totalOutput, totalThoughts, totalTokens, totalErrors, totalRefusals, aggregatedErrorsGrouped, overallCacheRate, agentModelStats } = aggregateRunsTokenStats(runs);
  const rows = Object.values(agentModelStats).map((m) => {
    const errVal = m.errors || 0;
    const errCell = errVal > 0
      ? `<strong style="color: var(--severity-high);">${errVal.toLocaleString()}</strong>`
      : `<span style="color: var(--status-resolved);">0</span>`;
    return `
    <tr>
      <td><strong>${m.agent}</strong> (<code>${m.model}</code>)</td>
      <td>${(m.uncached_tokens || 0).toLocaleString()}</td>
      <td>${(m.cache_tokens || 0).toLocaleString()}</td>
      <td>${(m.thoughts_tokens || 0).toLocaleString()}</td>
      <td>${(m.output_tokens || 0).toLocaleString()}</td>
      <td><strong>${(m.total_tokens || 0).toLocaleString()}</strong></td>
      <td>${errCell}</td>
      <td>
        <button class="badge-btn" onclick="window.showTokenRunsModal('${encodeURIComponent(m.key)}')">${m.runs.length} Runs</button>
      </td>
    </tr>
  `;
  }).join("");
  return renderCollapsibleTokenCard(totalInput, totalUncached, totalCached, totalOutput, totalThoughts, totalTokens, overallCacheRate, rows, true, totalErrors, totalRefusals, aggregatedErrorsGrouped);
}

export function renderProjectTokenUsage(projRuns) {
  const { totalInput, totalUncached, totalCached, totalOutput, totalThoughts, totalTokens, totalErrors, totalRefusals, aggregatedErrorsGrouped, overallCacheRate, agentModelStats } = aggregateRunsTokenStats(projRuns);
  const rows = Object.values(agentModelStats).map((m) => {
    const errVal = m.errors || 0;
    const errCell = errVal > 0
      ? `<strong style="color: var(--severity-high);">${errVal.toLocaleString()}</strong>`
      : `<span style="color: var(--status-resolved);">0</span>`;
    return `
    <tr>
      <td><strong>${m.agent}</strong> (<code>${m.model}</code>)</td>
      <td>${(m.uncached_tokens || 0).toLocaleString()}</td>
      <td>${(m.cache_tokens || 0).toLocaleString()}</td>
      <td>${(m.thoughts_tokens || 0).toLocaleString()}</td>
      <td>${(m.output_tokens || 0).toLocaleString()}</td>
      <td><strong>${(m.total_tokens || 0).toLocaleString()}</strong></td>
      <td>${errCell}</td>
      <td>
        <button class="badge-btn" onclick="window.showTokenRunsModal('${encodeURIComponent(m.key)}')">${m.runs.length} Runs</button>
      </td>
    </tr>
  `;
  }).join("");
  return renderCollapsibleTokenCard(totalInput, totalUncached, totalCached, totalOutput, totalThoughts, totalTokens, overallCacheRate, rows, true, totalErrors, totalRefusals, aggregatedErrorsGrouped);
}

export function renderRunTokenUsage(data) {
  const tokenUsage = (data && data.token_usage) || {};
  const tot = tokenUsage.total || {};
  const prompt = tot.total_input_tokens ?? tot.prompt_tokens ?? 0;
  const uncached = tot.uncached_tokens ?? (prompt - (tot.cache_tokens || 0));
  const cached = tot.cache_tokens ?? 0;
  const comp = tot.output_tokens ?? tot.total_output_tokens ?? tot.completion_tokens ?? 0;
  const thoughts = tot.thoughts_tokens ?? 0;
  const totalTokens = tot.total_tokens ?? (prompt + comp + thoughts);
  const totalErrors = tot.total_errors ?? tot.errors ?? 0;
  const errorsGrouped = tokenUsage.errors_grouped || {};
  const refusals = countRefusalsFromGrouped(errorsGrouped);
  const cacheHitRate = prompt > 0 && cached > 0 ? `${((cached / prompt) * 100).toFixed(1)}%` : "0.0%";
  const byAgent = tokenUsage.by_agent || {};
  const byModel = tokenUsage.by_model || {};

  const rows = [];
  if (Object.keys(byAgent).length > 0) {
    Object.entries(byAgent).forEach(([agentName, stats]) => {
      const inp = stats.total_input_tokens ?? stats.prompt_tokens ?? 0;
      const uncache = stats.uncached_tokens ?? (inp - (stats.cache_tokens || 0));
      const cache = stats.cache_tokens ?? 0;
      const out = stats.output_tokens ?? 0;
      const th = stats.thoughts_tokens ?? 0;
      const tok = stats.total_tokens ?? (inp + out + th);
      const errCount = stats.errors ?? 0;
      const errCell = errCount > 0
        ? `<strong style="color: var(--severity-high);">${errCount.toLocaleString()}</strong>`
        : `<span style="color: var(--status-resolved);">0</span>`;
      rows.push(`
        <tr>
          <td><strong>${agentName}</strong> (<code>${stats.model || "Unknown"}</code>)</td>
          <td>${uncache.toLocaleString()}</td>
          <td>${cache.toLocaleString()}</td>
          <td>${th.toLocaleString()}</td>
          <td>${out.toLocaleString()}</td>
          <td><strong>${tok.toLocaleString()}</strong></td>
          <td>${errCell}</td>
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
          <td>0</td>
          <td>0</td>
          <td>${out.toLocaleString()}</td>
          <td><strong>${tok.toLocaleString()}</strong></td>
          <td><span style="color: var(--status-resolved);">0</span></td>
        </tr>
      `);
    });
  } else if (totalTokens > 0 || totalErrors > 0) {
    const modelName = (data && data.metadata && data.metadata.model) || "Default";
    const errCell = totalErrors > 0
      ? `<strong style="color: var(--severity-high);">${totalErrors.toLocaleString()}</strong>`
      : `<span style="color: var(--status-resolved);">0</span>`;
    rows.push(`
      <tr>
        <td><code>${modelName}</code></td>
        <td>${uncached.toLocaleString()}</td>
        <td>${cached.toLocaleString()}</td>
        <td>${thoughts.toLocaleString()}</td>
        <td>${comp.toLocaleString()}</td>
        <td><strong>${totalTokens.toLocaleString()}</strong></td>
        <td>${errCell}</td>
      </tr>
    `);
  }

  return renderCollapsibleTokenCard(prompt, uncached, cached, comp, thoughts, totalTokens, cacheHitRate, rows.join(""), false, totalErrors, refusals, errorsGrouped);
}

