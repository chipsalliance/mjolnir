// Shared Mjolnir Dashboard Logic (MPA Version)

const safeStorage = {
    getItem(key) {
        try {
            return localStorage.getItem(key);
        } catch (e) {
            console.warn(`Error reading ${key} from localStorage:`, e);
            return null;
        }
    },
    setItem(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (e) {
            console.warn(`Error writing ${key} to localStorage:`, e);
        }
    }
};

let activeFindings = [];
let projectFindingsLimit = 20;
let jobFindingsLimit = 20;

// Theme Toggle
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    safeStorage.setItem('mjolnir-theme', next);
    updateThemeToggleButton(next);
    
    // Redraw Sankey on theme change (colors are theme-dependent)
    if (pageData && pageData.sankeyRows) {
        let rows = pageData.sankeyRows;
        if (pageData.type === 'global') {
            const hideTests = safeStorage.getItem('mjolnir-hide-tests') === 'true';
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
    const theme = safeStorage.getItem('mjolnir-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeToggleButton(theme);
}

// "Hide Test Runs" Toggling
let hideTests = safeStorage.getItem('mjolnir-hide-tests') === 'true';

function applyHideTests() {
    document.querySelectorAll('.is-test-item').forEach(el => {
        el.style.display = hideTests ? 'none' : '';
    });
}

function toggleHideTests(checked) {
    safeStorage.setItem('mjolnir-hide-tests', checked);
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
        populateProjectFilters();
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

// Markdown helpers
function parseMarkdown(text) {
    if (!text) return '';
    if (typeof marked !== 'undefined' && marked.parse) {
        try {
            return marked.parse(text);
        } catch (e) {
            console.error("Failed to parse markdown:", e);
        }
    }
    // Fallback: escape HTML
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function getMdContentHtml(text) {
    if (!text) return '';
    const isRaw = typeof marked === 'undefined';
    const content = parseMarkdown(text);
    const style = isRaw ? ' style="white-space: pre-wrap;"' : '';
    return `<div class="md-content"${style}>${content}</div>`;
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
        card.className = `finding-card ${finding.severity.toLowerCase()}`;
        card.id = finding.id;

        // Format severity label
        let badgeClass = `badge badge-${finding.severity.toLowerCase()}`;
        
        let headerHtml = `
            <div class="finding-header">
                <span class="${badgeClass}">${finding.severity}</span>
                <span class="finding-id" style="font-size:11px; font-family: monospace; color:var(--text-muted); margin-left: 8px;">ID: ${finding.id}</span>
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
                    ${getMdContentHtml(finding.description)}
                </div>
                ${finding.recommendation ? `
                <div class="details-section">
                    <strong>Recommendation:</strong>
                    ${getMdContentHtml(finding.recommendation)}
                </div>` : ''}
                ${finding.attack_vector ? `
                <div class="details-section">
                    <strong>Attack Vector:</strong>
                    ${getMdContentHtml(finding.attack_vector)}
                </div>` : ''}
                ${finding.justification ? `
                <div class="details-section">
                    <strong>Justification:</strong>
                    ${getMdContentHtml(finding.justification)}
                </div>` : ''}
            </div>
        `;
        container.appendChild(card);
    });

    // After appending all cards, highlight code blocks
    if (typeof hljs !== 'undefined') {
        container.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });
    }
}

// Copy link to finding card
function copyCardLink(cardId) {
    const url = new URL(window.location.href);
    url.hash = cardId;
    navigator.clipboard.writeText(url.toString()).then(() => {
        const card = document.getElementById(cardId);
        const btn = card ? card.querySelector('.copy-link-btn') : null;
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
function populateProjectFilters() {
    if (!pageData.runs) return;

    const modelFilter = document.getElementById('project-model-filter');
    const runFilter = document.getElementById('project-run-filter');

    if (!modelFilter || !runFilter) return;

    modelFilter.innerHTML = '<option value="all">All Models</option>';
    runFilter.innerHTML = '<option value="all">All Runs</option>';

    const models = new Set();
    const runs = [];

    pageData.runs.forEach(run => {
        if (run.model) models.add(run.model);
        runs.push({
            folder: run.run_folder,
            name: run.name,
            timestamp: run.timestamp
        });
    });

    Array.from(models).sort().forEach(model => {
        const opt = document.createElement('option');
        opt.value = model;
        opt.textContent = model;
        modelFilter.appendChild(opt);
    });

    runs.sort((a, b) => b.timestamp.localeCompare(a.timestamp));

    runs.forEach(run => {
        const opt = document.createElement('option');
        opt.value = run.folder;
        opt.textContent = `${run.name} (${run.folder})`;
        runFilter.appendChild(opt);
    });
}

function getSankeyRowsJS(filteredRuns) {
    if (!filteredRuns || filteredRuns.length === 0) return [];

    const records = [];
    filteredRuns.forEach(r => {
        if (r.flow) {
            records.push(...r.flow);
        }
    });

    if (records.length === 0) return [];

    const phaseMap = {};
    records.forEach(r => {
        if (r.history) {
            r.history.forEach(h => {
                phaseMap[String(h.phase_id)] = h.phase_name;
            });
        }
    });

    const phaseKeys = Object.keys(phaseMap).sort((a, b) => Number(a) - Number(b));
    if (phaseKeys.length < 2) return [];

    const nodeCounts = {};
    const recordBases = [];

    records.forEach(r => {
        const history = r.history || [];
        const phaseNodeNames = {};
        
        phaseKeys.forEach(pKey => {
            const snap = history.find(h => String(h.phase_id) === pKey);
            if (!snap) return;

            const phaseName = phaseMap[pKey];
            const severity = snap.severity || "Unknown";
            const verdict = snap.verdict;

            let nodeName;
            if (verdict === "False Positive") {
                nodeName = `Phase ${pKey}: ${phaseName} - Closed`;
            } else if (severity === "Skipped") {
                nodeName = `Phase ${pKey}: ${phaseName} - Skipped`;
            } else {
                nodeName = `Phase ${pKey}: ${phaseName} - ${severity}`;
            }
            phaseNodeNames[pKey] = nodeName;
        });

        for (let i = 0; i < phaseKeys.length - 1; i++) {
            const pKey1 = phaseKeys[i];
            const pKey2 = phaseKeys[i + 1];
            const base1 = phaseNodeNames[pKey1];
            const base2 = phaseNodeNames[pKey2];

            if (base1 && base2) {
                nodeCounts[base1] = (nodeCounts[base1] || 0) + 1;
                nodeCounts[base2] = (nodeCounts[base2] || 0) + 1;
                recordBases.push([base1, base2]);
            }
        }
    });

    if (recordBases.length === 0) return [];

    const nodesByPhase = {};
    recordBases.forEach(([base1, base2]) => {
        [base1, base2].forEach(node => {
            const match = node.match(/Phase (\d+):/);
            if (match) {
                const phaseNum = match[1];
                if (!nodesByPhase[phaseNum]) {
                    nodesByPhase[phaseNum] = new Set();
                }
                nodesByPhase[phaseNum].add(node);
            }
        });
    });

    const severityOrder = {
        "Closed": 0,
        "Skipped": 0,
        "Excluded": 0,
        "Informational": 1,
        "Low": 2,
        "Medium": 3,
        "High": 4,
        "Critical": 5,
    };

    function getPriority(nodeName) {
        for (const [sev, priority] of Object.entries(severityOrder)) {
            if (nodeName.includes(sev)) return priority;
        }
        return 99;
    }

    const phaseNums = Object.keys(nodesByPhase).sort((a, b) => Number(a) - Number(b));
    const dummyRows = [];
    for (let i = 0; i < phaseNums.length - 1; i++) {
        const p1 = phaseNums[i];
        const p2 = phaseNums[i + 1];

        const sortedSrcs = Array.from(nodesByPhase[p1]).sort((a, b) => getPriority(a) - getPriority(b));
        const sortedDsts = Array.from(nodesByPhase[p2]).sort((a, b) => getPriority(a) - getPriority(b));

        const maxLen = Math.max(sortedSrcs.length, sortedDsts.length);
        for (let j = 0; j < maxLen; j++) {
            const src = sortedSrcs[Math.min(j, sortedSrcs.length - 1)];
            const dst = sortedDsts[Math.min(j, sortedDsts.length - 1)];
            dummyRows.push([src, dst]);
        }
    }

    const transitions = {};
    recordBases.forEach(([base1, base2]) => {
        const state1 = `${base1} (count: ${nodeCounts[base1]})`;
        const state2 = `${base2} (count: ${nodeCounts[base2]})`;
        const key = `${state1}::${state2}`;
        transitions[key] = (transitions[key] || 0) + 1;
    });

    const realRows = [];
    for (const [key, weight] of Object.entries(transitions)) {
        const [src, dst] = key.split("::");
        realRows.push([src, dst, weight]);
    }

    realRows.sort((a, b) => {
        const prioA = getPriority(a[0]) - getPriority(b[0]);
        if (prioA !== 0) return prioA;
        return getPriority(a[1]) - getPriority(b[1]);
    });

    const finalDummyRows = [];
    dummyRows.forEach(([srcBase, dstBase]) => {
        const srcName = `${srcBase} (count: ${nodeCounts[srcBase]})`;
        const dstName = `${dstBase} (count: ${nodeCounts[dstBase]})`;
        finalDummyRows.push([srcName, dstName, 0]);
    });

    return [...finalDummyRows, ...realRows];
}

// Project View filtering and sorting
function applyProjectFilters() {
    const searchVal = document.getElementById('project-search-input').value.toLowerCase();
    const sevFilter = document.getElementById('project-severity-filter').value;
    const modelFilter = document.getElementById('project-model-filter').value;
    const runFilter = document.getElementById('project-run-filter').value;
    const sortOrder = document.getElementById('project-sort-order').value;
    let filtered = activeFindings;

    if (sevFilter !== 'all') {
        const targetRank = getSeverityRank(sevFilter);
        filtered = filtered.filter(f => getSeverityRank(f.severity) >= targetRank);
    }

    if (modelFilter !== 'all') {
        filtered = filtered.filter(f => f.model === modelFilter);
    }

    if (runFilter !== 'all') {
        filtered = filtered.filter(f => f.run_folder === runFilter);
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

    // Update Sankey
    if (pageData.runs) {
        let filteredRuns = pageData.runs;
        if (modelFilter !== 'all') {
            filteredRuns = filteredRuns.filter(r => r.model === modelFilter);
        }
        if (runFilter !== 'all') {
            filteredRuns = filteredRuns.filter(r => r.run_folder === runFilter);
        }
        const newSankeyRows = getSankeyRowsJS(filteredRuns);
        drawSankeyChart(newSankeyRows, 'overview-sankey-chart');
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
