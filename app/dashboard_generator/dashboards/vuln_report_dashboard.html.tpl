<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vulnerability Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">

    <!-- Highlight.js for elegant Rust syntax highlighting -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/github-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/languages/rust.min.js"></script>

    <style>
{{dashboard_css}}
        /* Extra styles for metadata */
        .metadata-section {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 20px;
            font-size: 0.9em;
        }
        .metadata-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 10px;
        }
        .metadata-item {
            color: #8b949e;
        }
        .metadata-item strong {
            color: #c9d1d9;
        }
        .metadata-item a {
            color: #58a6ff;
            text-decoration: none;
        }
        .metadata-item a:hover {
            text-decoration: underline;
        }
        code.commit {
            font-family: 'Fira Code', monospace;
            background-color: #111;
            padding: 2px 6px;
            border-radius: 4px;
            color: #ff7b72;
        }
  </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Vulnerability Dashboard</h1>
            <div class="badge sev-Informational" id="count-display">0 Vulnerabilities</div>
        </header>

        <div id="metadata-container" class="metadata-section" style="display: none;">
            <!-- Metadata will be rendered here -->
        </div>

        <div class="metrics">
            <div class="metric-card" style="border-top: 4px solid var(--critical-color)">
                <div class="metric-value" id="metric-critical" style="color: var(--critical-color)">0</div>
                <div class="metric-label">Critical</div>
            </div>
            <div class="metric-card" style="border-top: 4px solid var(--high-color)">
                <div class="metric-value" id="metric-high" style="color: var(--high-color)">0</div>
                <div class="metric-label">High</div>
            </div>
            <div class="metric-card" style="border-top: 4px solid var(--medium-color)">
                <div class="metric-value" id="metric-medium" style="color: var(--medium-color)">0</div>
                <div class="metric-label">Medium</div>
            </div>
            <div class="metric-card" style="border-top: 4px solid var(--low-color)">
                <div class="metric-value" id="metric-low" style="color: var(--low-color)">0</div>
                <div class="metric-label">Low</div>
            </div>
            <div class="metric-card" style="border-top: 4px solid var(--accent-color)">
                <div class="metric-value" id="metric-total">0</div>
                <div class="metric-label">Total</div>
            </div>
        </div>

        <div class="controls">
            <div class="control-group">
                <label for="filter-severity">Severity</label>
                <select id="filter-severity">
                    <option value="all">All Severities</option>
                    <option value="Critical">Critical</option>
                    <option value="High">High</option>
                    <option value="Medium">Medium</option>
                    <option value="Low">Low</option>
                    <option value="Informational">Informational</option>
                </select>
            </div>

            <div class="control-group">
                <label for="sort-by">Sort By</label>
                <select id="sort-by">
                    <option value="severity-desc">Severity (High to Low)</option>
                    <option value="severity-asc">Severity (Low to High)</option>
                    <option value="filename-asc">File Name (A-Z)</option>
                    <option value="filename-desc">File Name (Z-A)</option>
                </select>
            </div>

            <div class="control-group">
                <label for="group-by">Group By</label>
                <select id="group-by">
                    <option value="none">None</option>
                    <option value="directory">Parent Directory</option>
                    <option value="severity">Severity</option>
                </select>
            </div>
        </div>

        <div id="vuln-grid" class="grid"></div>
    </div>

    <script>
        const allVulns = {{vulns_json}};
        const metadata = {{metadata_json}};

        const filterSelect = document.getElementById('filter-severity');
        const sortSelect = document.getElementById('sort-by');
        const groupSelect = document.getElementById('group-by');
        const grid = document.getElementById('vuln-grid');
        const countDisplay = document.getElementById('count-display');

        function renderMarkdown(text) {
            if (!text) return '';

            // Escaping HTML
            let escaped = text
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');

            // Code blocks
            let lines = escaped.split('\n');
            let inCodeBlock = false;
            let htmlResult = [];

            for (let i = 0; i < lines.length; i++) {
                let line = lines[i];

                if (line.startsWith('```')) {
                    if (!inCodeBlock) {
                        let lang = line.slice(3).trim() || 'rust';
                        htmlResult.push(`<pre><code class="language-${lang}">`);
                        inCodeBlock = true;
                    } else {
                        htmlResult.push(`</code></pre>`);
                        inCodeBlock = false;
                    }
                    continue;
                }

                if (inCodeBlock) {
                    htmlResult.push(line + '\n');
                    continue;
                }

                // Extract inline code to protect it from formatting
                let inlineCodes = [];
                let processedLine = line.replace(/`([^`]+)`/g, function(match, codeSegment) {
                    inlineCodes.push(codeSegment);
                    return `@@INLINE_CODE_${inlineCodes.length - 1}@@`; // Changed to @@
                });

                // Apply formatting, using negative lookarounds to prevent intra-word emphasis
                processedLine = processedLine
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/(?<!\w)__(.*?)__(?!\w)/g, '<strong>$1</strong>')
                    .replace(/\*(.*?)\*/g, '<em>$1</em>')
                    .replace(/(?<!\w)_(.*?)_(?!\w)/g, '<em>$1</em>');

                // Restore inline code
                processedLine = processedLine.replace(/@@INLINE_CODE_(\d+)@@/g, function(match, index) {
                    return `<code>${inlineCodes[index]}</code>`;
                });

                htmlResult.push(processedLine + '\n');
            }

            return htmlResult.join('');
        }

        function createCard(vuln, index) {
            const severityClass = `sev-${vuln.severity_normalized}`;
            return `
                <div class="card" id="card-${index}">
                    <div class="card-header"
                         onclick="toggleCard(${index})"
                         onkeydown="handleCardKey(event, ${index})"
                         tabindex="0"
                         role="button"
                         aria-expanded="false"
                         aria-controls="body-${index}">
                        <div class="card-header-title">${vuln.title}</div>
                        <span class="badge ${severityClass}">${vuln.severity_normalized}</span>
                    </div>
                    <div class="card-body" id="body-${index}">
                        <div class="file-info">📂 <strong>Path:</strong> ${vuln.file_path}</div>
                        <div class="description md-content">${renderMarkdown(vuln.description)}</div>
                    </div>
                </div>
            `;
        }

        window.toggleCard = function(index) {
            const card = document.getElementById(`card-${index}`);
            const header = card.querySelector('.card-header');
            if (card) {
                const isExpanded = card.classList.toggle('expanded');
                header.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');

                // Trigger syntax highlighting when card is opened
                if (isExpanded) {
                    card.querySelectorAll('pre code').forEach((el) => {
                        hljs.highlightElement(el);
                    });
                }
            }
        }

        window.handleCardKey = function(event, index) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                toggleCard(index);
            }
        }

        function updateMetrics(filtered) {
            const counts = { Critical: 0, High: 0, Medium: 0, Low: 0 };
            allVulns.forEach(v => {
                if (counts[v.severity_normalized] !== undefined) {
                    counts[v.severity_normalized]++;
                }
            });

            document.getElementById('metric-critical').textContent = counts.Critical;
            document.getElementById('metric-high').textContent = counts.High;
            document.getElementById('metric-medium').textContent = counts.Medium;
            document.getElementById('metric-low').textContent = counts.Low;
            document.getElementById('metric-total').textContent = allVulns.length;
        }

        function render() {
            // Filter
            let filtered = allVulns.filter(v =>
                filterSelect.value === 'all' || v.severity_normalized === filterSelect.value
            );

            // Sort
            const [sortField, sortDir] = sortSelect.value.split('-');
            filtered.sort((a, b) => {
                let valA, valB;
                if (sortField === 'severity') {
                    valA = a.sev_score;
                    valB = b.sev_score;
                } else if (sortField === 'filename') {
                    valA = a.file_name.toLowerCase();
                    valB = b.file_name.toLowerCase();
                }

                if (valA < valB) return sortDir === 'asc' ? -1 : 1;
                if (valA > valB) return sortDir === 'asc' ? 1 : -1;
                return 0;
            });

            // Group and Render
            grid.innerHTML = '';
            countDisplay.textContent = `${filtered.length} Vulnerabilit${filtered.length === 1 ? 'y' : 'ies'}`;

            updateMetrics(filtered);

            if (filtered.length === 0) {
                grid.innerHTML = `
                    <div class="zero-state">
                        <div class="zero-state-icon">🛡️</div>
                        <h3>No Vulnerabilities Found</h3>
                        <p>No security findings match your current filter criteria.</p>
                    </div>
                `;
                return;
            }

            if (groupSelect.value === 'none') {
                grid.innerHTML = filtered.map((v, i) => createCard(v, i)).join('');
            } else {
                const grouped = {};
                filtered.forEach((v, i) => {
                    const key = groupSelect.value === 'directory' ? v.parent_dir : v.severity_normalized;
                    if (!grouped[key]) grouped[key] = [];
                    grouped[key].push({v, i});
                });

                // Sort group keys
                const keys = Object.keys(grouped).sort();
                if (groupSelect.value === 'severity' && sortField === 'severity') {
                    keys.sort((a, b) => {
                        const order = { 'Critical': 5, 'High': 4, 'Medium': 3, 'Low': 2, 'Informational': 1 };
                        return sortDir === 'desc' ? order[b] - order[a] : order[a] - order[b];
                    });
                }

                keys.forEach(key => {
                    const header = document.createElement('div');
                    header.className = 'group-header';
                    header.innerHTML = `<span>📁</span> ${key}`;
                    grid.appendChild(header);

                    grouped[key].forEach(item => {
                        grid.insertAdjacentHTML('beforeend', createCard(item.v, item.i));
                    });
                });
            }
        }

        filterSelect.addEventListener('change', render);
        sortSelect.addEventListener('change', render);
        groupSelect.addEventListener('change', render);

        function renderMetadata() {
            const container = document.getElementById('metadata-container');
            if (!metadata || Object.keys(metadata).length === 0) {
                return;
            }
            container.style.display = 'block';
            
            let html = '<div class="metadata-grid">';
            if (metadata.timestamp) {
                html += `<div class="metadata-item"><strong>Timestamp:</strong> ${metadata.timestamp}</div>`;
            }
            if (metadata.orchestrator_commit) {
                html += `<div class="metadata-item"><strong>Orchestrator Commit:</strong> <code class="commit">${metadata.orchestrator_commit.substring(0, 7)}</code></div>`;
            }
            if (metadata.target_repo) {
                html += `<div class="metadata-item"><strong>Target Repository:</strong> <a href="${metadata.target_repo}" target="_blank">${metadata.target_repo}</a></div>`;
            }
            if (metadata.target_commit) {
                html += `<div class="metadata-item"><strong>Target Commit:</strong> <code class="commit">${metadata.target_commit.substring(0, 7)}</code></div>`;
            }
            html += '</div>';
            container.innerHTML = html;
        }

        renderMetadata();

        // Initial render
        render();
    </script>
</body>
</html>
