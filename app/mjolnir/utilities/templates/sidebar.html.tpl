<!-- Licensed under the Apache-2.0 license -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<aside class="sidebar">
    <div class="sidebar-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2 style="margin: 0; font-size: 20px; color: var(--text-bright);">Mjolnir</h2>
            <button id="theme-toggle" onclick="toggleTheme()" style="background: none; border: none; font-size: 16px; cursor: pointer; padding: 4px; outline: none; border-radius: 4px; line-height: 1;">🌙</button>
        </div>
        <span class="version" style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Security Platform</span>
        <div style="margin-top: 15px; font-size: 13px; color: var(--text-muted); display: flex; align-items: center; gap: 8px;">
            <input type="checkbox" id="toggle-hide-tests" onchange="toggleHideTests(this.checked)" style="cursor:pointer;">
            <label for="toggle-hide-tests" style="cursor:pointer; user-select:none;">Hide Test Runs</label>
        </div>
    </div>
    <nav class="sidebar-menu">
        <a href="#" class="menu-item active" id="menu-overview" onclick="clearProjectFilter()">📊 Overview</a>
        <div class="menu-label">Projects</div>
        <div id="job-menu-list">
            <!-- Dynamically populated -->
        </div>
        <div class="menu-label">Recent Runs</div>
        <div id="recent-runs-menu-list" style="display: flex; flex-direction: column; gap: 4px;">
            <!-- Dynamically populated -->
        </div>
    </nav>
</aside>
