<section id="view-overview" class="view-section">
    <div class="view-header" style="display: flex; align-items: center; justify-content: space-between;">
        <div>
            <h1 id="overview-title">Security Scan Overview</h1>
            <span id="overview-subtitle" style="font-size:13px; color:#8b949e; display:none; margin-top:5px; display:inline-block;"></span>
        </div>
    </div>

    <!-- Flow Evolution Card -->
    <div class="card" style="margin-bottom: 25px; padding: 20px;">
        <h3 id="overview-sankey-title" style="margin-top: 0; margin-bottom: 15px; color: var(--text-bright);">Vulnerability Flow Evolution</h3>
        <div id="overview-sankey-chart" style="height: 280px;"></div>
    </div>

    <!-- Projects Summary Card -->
    <div class="card" id="card-projects-summary" style="padding: 20px; display: block; margin-bottom: 25px;">
        <h3 style="margin-top: 0; color: var(--text-bright);">Projects Summary</h3>
        <table class="jobs-table">
            <thead>
                <tr>
                    <th>Project Name</th>
                    <th>Total Runs</th>
                    <th>Vulnerabilities</th>
                    <th style="color: var(--critical-color)">Crit</th>
                    <th style="color: var(--high-color)">High</th>
                    <th style="color: var(--medium-color)">Med</th>
                    <th style="color: var(--low-color)">Low</th>
                </tr>
            </thead>
            <tbody id="overview-projects-body">
                {{projects_summary_rows}}
            </tbody>
        </table>
    </div>
</section>
