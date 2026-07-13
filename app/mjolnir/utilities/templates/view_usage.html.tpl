<section id="view-usage" class="view-section">
    <div class="view-header">
        <h1>Token Usage Tracking</h1>
        <p style="color: var(--text-muted);">Aggregated token usage analytics grouped by interval and model across all runs.</p>
    </div>

    <div class="card" style="margin-top: 20px; padding: 20px; border: 1px solid var(--surface-border); border-radius: 12px; background: var(--surface-color);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h3 style="margin: 0; color: var(--text-bright);">Token Usage (Input / Output Tokens)</h3>
            <select id="usage-interval-select" onchange="if(typeof onUsageIntervalChange === 'function') onUsageIntervalChange()" style="padding: 6px 12px; border-radius: 6px; border: 1px solid var(--surface-border); background: var(--background-color); color: var(--text-bright);">
                <option value="hour">Per Hour</option>
                <option value="day" selected>Per Day</option>
                <option value="week">Per Week</option>
            </select>
        </div>
        <div style="width: 100%; overflow-x: auto;">
            <div id="usage-chart-container" style="min-width: 800px; height: 500px;"></div>
        </div>
    </div>

    <div class="card" style="margin-top: 20px; padding: 20px; border: 1px solid var(--surface-border); border-radius: 12px; background: var(--surface-color);">
        <h3 style="margin-top: 0; color: var(--text-bright); margin-bottom: 20px;">Token Breakdown by Model</h3>
        <div id="usage-breakdown-container" style="width: 100%;"></div>
    </div>
</section>
