<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<section id="view-job" class="view-section">
    <div class="view-header">
        <h1 id="active-job-title">{{job_name}}</h1>
        <div class="job-meta">
            <span>Project: <strong id="active-job-project">{{project_name}}</strong></span>
            <span>Model: <strong id="active-job-model">{{model_name}}</strong></span>
            <span>Target Commit: <code id="active-job-commit" class="commit">{{commit_hash_short}}</code></span>
            <span>Mode: <strong id="active-job-mode">{{pipeline_mode}}</strong></span>
            <span>Status: <strong id="active-job-status" style="color: {{status_color}}">{{status}}</strong></span>
            <span>Run: <strong id="active-job-run">{{run_folder}}</strong></span>
            <span>Scan Time: <strong id="active-job-timestamp">{{timestamp}}</strong></span>
            <span>Total Tokens: <strong id="active-job-tokens">{{total_tokens}}</strong></span>
        </div>
        
        {{errors_block}}

        <div id="job-sankey-container" class="card" style="margin-top: 20px; margin-bottom: 25px; padding: 15px; border: 1px solid var(--surface-border); border-radius: 12px;">
            <h3 style="margin-top: 0; color: var(--text-bright); margin-bottom: 15px;">Generate Sankey Diagram</h3>
            <div id="job-sankey-chart" style="width: 100%; height: 350px;"></div>
        </div>

    <div class="controls" style="margin-bottom: 20px; padding: 0; border: none; background: transparent; display: flex; gap: 15px;">
        <div class="control-group" style="flex: 1; min-width: 200px;">
            <label for="search-input">Search Findings</label>
            <input type="text" id="search-input" placeholder="Search title, description, or file..." oninput="onJobSearch()" style="padding: 10px 15px; border: 1px solid var(--surface-border); border-radius: 8px; background: var(--input-bg); color: var(--text-color); font-size: 14px; outline: none; width: 100%;">
        </div>
        <div class="control-group" style="width: 220px;">
            <label for="filter-severity">Severity Filter</label>
            <select id="filter-severity" onchange="onJobSearch()" style="padding: 10px 15px; border: 1px solid var(--surface-border); border-radius: 8px; background: var(--input-bg); color: var(--text-color); font-size: 14px; outline: none; width: 100%; cursor: pointer;">
                <option value="all">All Severities</option>
                <option value="critical">Critical</option>
                <option value="high">High & Higher</option>
                <option value="medium">Medium & Higher</option>
                <option value="low">Low & Higher</option>
            </select>
        </div>
        <div class="control-group" style="width: 200px;">
            <label for="job-sort-order">Sort Order</label>
            <select id="job-sort-order" onchange="onJobSearch()" style="padding: 10px 15px; border: 1px solid var(--surface-border); border-radius: 8px; background: var(--input-bg); color: var(--text-color); font-size: 14px; outline: none; width: 100%; cursor: pointer;">
                <option value="sev-desc">Severity (High to Low)</option>
                <option value="sev-asc">Severity (Low to High)</option>
            </select>
        </div>
        <div class="control-group" style="width: 200px;">
            <label for="job-view-mode">View Mode</label>
            <select id="job-view-mode" onchange="onJobSearch()" style="padding: 10px 15px; border: 1px solid var(--surface-border); border-radius: 8px; background: var(--input-bg); color: var(--text-color); font-size: 14px; outline: none; width: 100%; cursor: pointer;">
                <option value="list">List View</option>
                <option value="tree">Tree View</option>
            </select>
        </div>
    </div>

    <div class="grid" id="findings-container">
        <!-- Finding cards dynamically injected -->
    </div>
    <div id="job-load-more-container" style="text-align: center; margin-top: 20px; display: none;">
        <button onclick="loadMoreJobFindings()" style="padding: 10px 24px; background: var(--item-hover-bg); color: var(--text-color); border: 1px solid var(--surface-border); border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s;">Show More Findings</button>
    </div>
</section>
