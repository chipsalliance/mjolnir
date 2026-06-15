// Shared Mjolnir Dashboard Logic (MPA Version)

let activeFindings = [];
let projectFindingsLimit = 20;
let jobFindingsLimit = 20;

// Theme Toggle
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('mjolnir-theme', next);
    updateThemeToggleButton(next);
    
    // Redraw Sankey on theme change (colors are theme-dependent)
    if (pageData && pageData.sankeyRows) {
        let rows = pageData.sankeyRows;
        if (pageData.type === 'global') {
            const hideTests = localStorage.getItem('mjolnir-hide-tests') === 'true';
            rows = hideTests ? pageData.sankeyRowsNoTests : pageData.sankeyRowsAll;
        }
        drawSankeyChart(rows, pageData.type === 'run' ? 'job-sankey-chart' : 'overview-sankey-chart');
    }
}

function updateThemeToggleButton(theme) {
    const btn = document.getElementById('theme-toggle');
    if (btn) {
        btn.innerText = theme === 'dark' ? '☀️' : '🌙';
    }
}

function initTheme() {
    const theme = localStorage.getItem('mjolnir-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeToggleButton(theme);
}

// "Hide Test Runs" Toggling
let hideTests = localStorage.getItem('mjolnir-hide-tests') === 'true';

function applyHideTests() {
    document.querySelectorAll('.is-test-item').forEach(el => {
        el.style.display = hideTests ? 'none' : '';
    });
}

function toggleHideTests(checked) {
    localStorage.setItem('mjolnir-hide-tests', checked);
    hideTests = checked;
    applyHideTests();
    
    // If we are on the global overview page, we must switch the Sankey data
    if (pageData && pageData.type === 'global') {
        const rows = hideTests ? pageData.sankeyRowsNoTests : pageData.sankeyRowsAll;
        drawSankeyChart(rows, 'overview-sankey-chart');
    }
}

// Initialize Page
document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    
    // Setup hide-tests checkbox state on load
    const cb = document.getElementById('toggle-hide-tests');
    if (cb) {
        cb.checked = hideTests;
    }
    applyHideTests();
    
    initPage();
});

function initPage() {
    if (typeof pageData === 'undefined' || !pageData) return;

    if (pageData.type === 'global') {
        const rows = hideTests ? pageData.sankeyRowsNoTests : pageData.sankeyRowsAll;
        drawSankeyChart(rows, 'overview-sankey-chart');
    } else if (pageData.type === 'project') {
        drawSankeyChart(pageData.sankeyRows, 'overview-sankey-chart');
        activeFindings = pageData.findings;
        applyProjectFilters();
    } else if (pageData.type === 'run') {
        drawSankeyChart(pageData.sankeyRows, 'job-sankey-chart');
        activeFindings = pageData.findings;
        applyFilters();
    }
}

// Ranks
function getSeverityRank(sev) {
    if (!sev) return 0;
    const s = sev.toLowerCase().trim();
    if (s.includes('critical')) return 4;
    if (s.includes('high')) return 3;
    if (s.includes('medium')) return 2;
    if (s.includes('low')) return 1;
    return 0;
}

// findings renderer (generic)
function renderFindings(findings, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = '';

    if (findings.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted); background: var(--surface-color); border: 1px dashed var(--surface-border); border-radius: 8px;">
                🔍 No findings match search or filters.
            </div>
        `;
        return;
    }

    findings.forEach((finding, index) => {
        const card = document.createElement('div');
        card.className = `finding-card ${finding.severity ? finding.severity.toLowerCase() : 'informational'}`;
        card.id = `finding-card-${index}`;

        // Format severity label
        let badgeClass = 'badge-tbl';
        if (finding.severity) {
            badgeClass += ` badge-${finding.severity.toLowerCase()}`;
        }
        
        let headerHtml = `
            <div class="finding-header">
                <span class="${badgeClass}">${finding.severity || 'Informational'}</span>
                <span class="finding-id" style="font-size:11px; font-family: monospace; color:var(--text-muted); margin-left: 8px;">ID: ${finding.id || 'N/A'}</span>
                <span class="copy-link-btn" onclick="copyCardLink('${card.id}')" title="Copy link to this finding">🔗 Link</span>
            </div>
        `;

        let statusClass = 'status-badge';
        if (finding.status) {
             statusClass += ` status-${finding.status.toLowerCase()}`;
        }
        let statusHtml = finding.status ? `<span class="${statusClass}">${finding.status}</span>` : '';

        card.innerHTML = `
            ${headerHtml}
            <div class="finding-title" style="margin-top:8px;">${finding.title}</div>
            <div class="finding-file">File: <code>${finding.file}</code> : <span style="font-weight:600">${finding.location}</span></div>
            
            <div class="card-details">
                <div class="details-section">
                    <strong>Description:</strong>
                    <div class="md-content" style="white-space: pre-wrap;">${finding.description}</div>
                </div>
                ${finding.recommendation ? `
                <div class="details-section">
                    <strong>Recommendation:</strong>
                    <div class="md-content" style="white-space: pre-wrap;">${finding.recommendation}</div>
                </div>` : ''}
                ${finding.attack_vector ? `
                <div class="details-section">
                    <strong>Attack Vector:</strong>
                    <div class="md-content" style="white-space: pre-wrap;">${finding.attack_vector}</div>
                </div>` : ''}
                ${finding.justification ? `
                <div class="details-section">
                    <strong>Justification:</strong>
                    <div class="md-content" style="white-space: pre-wrap;">${finding.justification}</div>
                </div>` : ''}
            </div>
        `;
        container.appendChild(card);
    });
}

// Copy link to finding card
function copyCardLink(cardId) {
    const url = new URL(window.location.href);
    url.hash = cardId;
    navigator.clipboard.writeText(url.toString()).then(() => {
        const btn = document.querySelector(`#${cardId} .copy-link-btn`);
        if (btn) {
            const oldText = btn.innerText;
            btn.innerText = "Copied! ✓";
            setTimeout(() => btn.innerText = oldText, 2000);
        }
    }).catch(err => {
        console.error('Could not copy text: ', err);
    });
}

// Project View filtering and sorting
function applyProjectFilters() {
    const searchVal = document.getElementById('project-search-input').value.toLowerCase();
    const sevFilter = document.getElementById('project-severity-filter').value;
    const sortOrder = document.getElementById('project-sort-order').value;
    let filtered = activeFindings;

    if (sevFilter !== 'all') {
        const targetRank = getSeverityRank(sevFilter);
        filtered = filtered.filter(f => getSeverityRank(f.severity) >= targetRank);
    }

    if (searchVal) {
        filtered = filtered.filter(f => 
            f.title.toLowerCase().includes(searchVal) || 
            f.description.toLowerCase().includes(searchVal) ||
            f.file.toLowerCase().includes(searchVal)
        );
    }

    filtered.sort((a, b) => {
        const rankA = getSeverityRank(a.severity);
        const rankB = getSeverityRank(b.severity);
        return sortOrder === 'sev-desc' ? rankB - rankA : rankA - rankB;
    });

    const totalMatching = filtered.length;
    const paginated = filtered.slice(0, projectFindingsLimit);

    renderFindings(paginated, 'project-findings-container');

    const loadMoreContainer = document.getElementById('project-load-more-container');
    if (loadMoreContainer) {
        loadMoreContainer.style.display = totalMatching > projectFindingsLimit ? 'block' : 'none';
    }
}

function onProjectSearch() {
    projectFindingsLimit = 20;
    applyProjectFilters();
}

function loadMoreProjectFindings() {
    projectFindingsLimit += 20;
    applyProjectFilters();
}

// Run View filtering and sorting
function applyFilters() {
    const sevFilter = document.getElementById('filter-severity').value;
    const searchVal = document.getElementById('search-input').value.toLowerCase();
    const sortOrder = document.getElementById('job-sort-order').value;

    let filtered = activeFindings;

    if (sevFilter !== 'all') {
        const targetRank = getSeverityRank(sevFilter);
        filtered = filtered.filter(f => getSeverityRank(f.severity) >= targetRank);
    }

    if (searchVal) {
        filtered = filtered.filter(f => 
            f.title.toLowerCase().includes(searchVal) || 
            f.description.toLowerCase().includes(searchVal) ||
            f.file.toLowerCase().includes(searchVal)
        );
    }

    filtered.sort((a, b) => {
        const rankA = getSeverityRank(a.severity);
        const rankB = getSeverityRank(b.severity);
        return sortOrder === 'sev-desc' ? rankB - rankA : rankA - rankB;
    });

    const totalMatching = filtered.length;
    const paginated = filtered.slice(0, jobFindingsLimit);

    renderFindings(paginated, 'findings-container');

    const loadMoreContainer = document.getElementById('job-load-more-container');
    if (loadMoreContainer) {
        loadMoreContainer.style.display = totalMatching > jobFindingsLimit ? 'block' : 'none';
    }
}

function onJobSearch() {
    jobFindingsLimit = 20;
    applyFilters();
}

function loadMoreJobFindings() {
    jobFindingsLimit += 20;
    applyFilters();
}

// Google Charts Sankey renderer
function drawSankeyChart(rows, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Clear previous
    container.innerHTML = '';

    if (!rows || rows.length === 0) {
        container.innerHTML = `
            <div style="display:flex; justify-content:center; align-items:center; height:100%; color:var(--text-muted);">
                🌊 Flow history requires at least 2 analysis phases to render.
            </div>
        `;
        return;
    }

    if (typeof google === 'undefined' || !google.visualization || !google.visualization.Sankey) {
        // Wait for loader
        setTimeout(() => drawSankeyChart(rows, containerId), 100);
        return;
    }

    const data = new google.visualization.DataTable();
    data.addColumn('string', 'From');
    data.addColumn('string', 'To');
    data.addColumn('number', 'Weight');
    data.addRows(rows);

    // Extract unique nodes in order of appearance
    const uniqueNodes = [];
    rows.forEach(row => {
        if (!uniqueNodes.includes(row[0])) uniqueNodes.push(row[0]);
        if (!uniqueNodes.includes(row[1])) uniqueNodes.push(row[1]);
    });

    // Map severity names to matching colors
    const nodeColors = uniqueNodes.map(nodeName => {
        if (nodeName.includes('Critical')) return '#d93025';
        if (nodeName.includes('High')) return '#e8710a';
        if (nodeName.includes('Medium')) return '#f9ab00';
        if (nodeName.includes('Low')) return '#1e8e3e';
        if (nodeName.includes('Informational')) return '#1a73e8';
        if (nodeName.includes('Closed') || nodeName.includes('Skipped') || nodeName.includes('Excluded')) return '#70757a';
        return '#1a73e8'; // Fallback
    });

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const labelColor = isDark ? '#8b949e' : '#3c4043';

    const options = {
        sankey: {
            iterations: 0,
            node: {
                colors: nodeColors,
                nodePadding: 24,
                width: 18,
                label: { 
                    fontName: 'Segoe UI', 
                    fontSize: 12, 
                    color: labelColor, 
                    bold: true 
                }
            },
            link: {
                colorMode: 'gradient'
            }
        }
    };

    const chart = new google.visualization.Sankey(container);
    chart.draw(data, options);
}

// Initialize Google Charts loader
if (typeof google !== 'undefined') {
    google.charts.load('current', {'packages':['sankey']});
}
