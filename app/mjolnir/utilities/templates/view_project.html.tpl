<section id="view-overview" class="view-section">
    <div class="view-header" style="display: flex; align-items: center; justify-content: space-between;">
        <div>
            <h1 id="overview-title">Project: {{project_name}}</h1>
            <span id="overview-subtitle" style="font-size:13px; color:#8b949e; margin-top:5px; display:inline-block;">Project Filter Active</span>
        </div>
    </div>

    <!-- Flow Evolution Card -->
    <div class="card" style="margin-bottom: 25px; padding: 20px;">
        <h3 id="overview-sankey-title" style="margin-top: 0; margin-bottom: 15px; color: var(--text-bright);">Vulnerability Flow Evolution: {{project_name}}</h3>
        <div id="overview-sankey-chart" style="height: 280px;"></div>
    </div>

    <!-- Project Vulnerabilities Card -->
    <div class="card" id="card-project-findings" style="padding: 20px; display: block; margin-bottom: 25px;">
        <h3 style="margin-top: 0; color: var(--text-bright);"><span id="project-findings-title">Vulnerabilities: {{project_name}}</span></h3>
        
        <div class="controls" style="margin-bottom: 20px; padding: 0; border: none; background: transparent; display: flex; gap: 15px;">
            <div class="control-group" style="flex: 1; min-width: 200px;">
                <label for="project-search-input">Search Vulnerabilities</label>
                <input type="text" id="project-search-input" placeholder="Search title, description, or file..." oninput="onProjectSearch()" style="padding: 10px 15px; border: 1px solid var(--surface-border); border-radius: 8px; background: var(--input-bg); color: var(--text-color); font-size: 14px; outline: none; width: 100%;">
            </div>
            <div class="control-group" style="width: 220px;">
                <label for="project-severity-filter">Severity Filter</label>
                <select id="project-severity-filter" onchange="onProjectSearch()" style="padding: 10px 15px; border: 1px solid var(--surface-border); border-radius: 8px; background: var(--input-bg); color: var(--text-color); font-size: 14px; outline: none; width: 100%; cursor: pointer;">
                    <option value="all">All Severities</option>
                    <option value="critical">Critical</option>
                    <option value="high">High & Higher</option>
                    <option value="medium">Medium & Higher</option>
                    <option value="low">Low & Higher</option>
                </select>
            </div>
            <div class="control-group" style="width: 200px;">
                <label for="project-model-filter">Model Filter</label>
                <select id="project-model-filter" onchange="onProjectSearch()" style="padding: 10px 15px; border: 1px solid var(--surface-border); border-radius: 8px; background: var(--input-bg); color: var(--text-color); font-size: 14px; outline: none; width: 100%; cursor: pointer;">
                    <option value="all">All Models</option>
                </select>
            </div>
            <div class="control-group" style="width: 200px;">
                <label for="project-run-filter">Run Filter</label>
                <select id="project-run-filter" onchange="onProjectSearch()" style="padding: 10px 15px; border: 1px solid var(--surface-border); border-radius: 8px; background: var(--input-bg); color: var(--text-color); font-size: 14px; outline: none; width: 100%; cursor: pointer;">
                    <option value="all">All Runs</option>
                </select>
            </div>
            <div class="control-group" style="width: 200px;">
                <label for="project-sort-order">Sort Order</label>
                <select id="project-sort-order" onchange="onProjectSearch()" style="padding: 10px 15px; border: 1px solid var(--surface-border); border-radius: 8px; background: var(--input-bg); color: var(--text-color); font-size: 14px; outline: none; width: 100%; cursor: pointer;">
                    <option value="sev-desc">Severity (High to Low)</option>
                    <option value="sev-asc">Severity (Low to High)</option>
                </select>
            </div>
            <div class="control-group" style="width: 200px;">
                <label for="project-view-mode">View Mode</label>
                <select id="project-view-mode" onchange="onProjectSearch()" style="padding: 10px 15px; border: 1px solid var(--surface-border); border-radius: 8px; background: var(--input-bg); color: var(--text-color); font-size: 14px; outline: none; width: 100%; cursor: pointer;">
                    <option value="list">List View</option>
                    <option value="tree">Tree View</option>
                </select>
            </div>
        </div>

        <div class="grid" id="project-findings-container">
            <!-- Aggregated finding cards dynamically injected -->
        </div>
        <div id="project-load-more-container" style="text-align: center; margin-top: 20px; display: none;">
            <button onclick="loadMoreProjectFindings()" style="padding: 10px 24px; background: var(--item-hover-bg); color: var(--text-color); border: 1px solid var(--surface-border); border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s;">Show More Findings</button>
        </div>
    </div>
</section>
