# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import json
import re
from pathlib import Path
from utilities.logger import logger


def format_findings(
    findings: list,
    run_id_key: str = None,
    timestamp: str = None,
    model: str = None,
    run_folder: str = None,
) -> list:
    """Formats raw findings for visual dashboard rendering."""
    formatted = []
    for f in findings:
        file_path = f["file"]
        desc_parts = [f["description"]]
        for key, val in f.items():
            if key in [
                "file",
                "title",
                "severity",
                "description",
                "verdict",
                "justification",
                "attack_vector",
                "recommendation",
                "id",
                "status",
                "history",
                "location",
            ]:
                continue
            if val:
                display_key = key.replace("_", " ").title()
                desc_parts.append(f"**{display_key}:** {val}")

        item = {
            "id": f["id"],
            "file": file_path,
            "location": f["location"],
            "title": f["title"],
            "severity": f["severity"],
            "description": "\n\n".join(filter(None, desc_parts)),
            "verdict": f.get("verdict"),
            "justification": f.get("justification"),
            "attack_vector": f.get("attack_vector"),
            "recommendation": f["recommendation"],
        }
        if run_id_key:
            item["run_id_key"] = run_id_key
        if timestamp:
            item["timestamp"] = timestamp
        if model:
            item["model"] = model
        if run_folder:
            item["run_folder"] = run_folder
        formatted.append(item)
    return formatted


def format_scan_data(
    project_name: str,
    job_name: str,
    run_name: str,
    report_data: dict,
    metadata: dict,
    flow_records: list,
) -> dict:
    """Formats findings and returns a structured dictionary for the template renderer."""
    findings = report_data.get("vulnerabilities") or []
    run_id_key = f"{project_name}-{job_name}-{run_name}"
    return {
        "name": job_name.replace("_", " "),
        "project": project_name,
        "project_folder": project_name,
        "job_folder": job_name,
        "run_folder": run_name,
        "timestamp": metadata.get("timestamp", "unknown"),
        "model": metadata.get("model", "mock"),
        "commit": metadata.get("target_commit", "unknown"),
        "findings": format_findings(
            findings,
            run_id_key=run_id_key,
            timestamp=metadata.get("timestamp"),
            model=metadata.get("model"),
            run_folder=run_name,
        ),
        "flow": flow_records,
    }


def compute_project_stats(runs_data: dict) -> dict:
    """Computes project-level metadata stats (runs, total vulns, severities)."""
    projects = {}
    for run in runs_data.values():
        proj = run["project"]
        if proj not in projects:
            projects[proj] = {
                "totalRuns": 0,
                "totalVulns": 0,
                "bySeverity": {
                    "Critical": 0,
                    "High": 0,
                    "Medium": 0,
                    "Low": 0,
                    "Informational": 0,
                },
            }

        p = projects[proj]
        p["totalRuns"] += 1
        p["totalVulns"] += len(run["findings"])

        for f in run["findings"]:
            sev = f.get("severity", "Informational")
            if "critical" in sev.lower():
                p["bySeverity"]["Critical"] += 1
            elif "high" in sev.lower():
                p["bySeverity"]["High"] += 1
            elif "medium" in sev.lower():
                p["bySeverity"]["Medium"] += 1
            elif "low" in sev.lower():
                p["bySeverity"]["Low"] += 1
            else:
                p["bySeverity"]["Informational"] += 1
    return projects


def get_sankey_rows(filtered_runs: list) -> list:
    """Pre-computes node transitions and orders them cleanly for Google Charts Sankey."""
    if not filtered_runs:
        return []

    records = []
    for r in filtered_runs:
        flow = r.get("flow")
        if flow:
            records.extend(flow)

    if not records:
        return []

    phase_map = {}
    for r in records:
        history = r.get("history")
        if history:
            for h in history:
                phase_map[str(h.get("phase_id"))] = h.get("phase_name")

    phase_keys = sorted(list(phase_map.keys()), key=lambda x: int(x))
    if len(phase_keys) < 2:
        return []

    node_counts = {}
    record_bases = []

    for r in records:
        history = r.get("history") or []
        phase_node_names = {}
        for p_key in phase_keys:
            snap = next((h for h in history if str(h.get("phase_id")) == p_key), None)
            if not snap:
                continue

            phase_name = phase_map[p_key]
            severity = snap.get("severity") or "Unknown"
            verdict = snap.get("verdict")

            if verdict == "False Positive":
                node_name = f"Phase {p_key}: {phase_name} - Closed"
            elif severity == "Skipped":
                node_name = f"Phase {p_key}: {phase_name} - Skipped"
            else:
                node_name = f"Phase {p_key}: {phase_name} - {severity}"
            phase_node_names[p_key] = node_name

        for i in range(len(phase_keys) - 1):
            p_key1 = phase_keys[i]
            p_key2 = phase_keys[i + 1]
            base1 = phase_node_names.get(p_key1)
            base2 = phase_node_names.get(p_key2)

            if base1 and base2:
                node_counts[base1] = node_counts.get(base1, 0) + 1
                node_counts[base2] = node_counts.get(base2, 0) + 1
                record_bases.append((base1, base2))

    if not record_bases:
        return []

    nodes_by_phase = {}
    for base1, base2 in record_bases:
        for node in [base1, base2]:
            match = re.search(r"Phase (\d+):", node)
            if match:
                phase_num = match.group(1)
                if phase_num not in nodes_by_phase:
                    nodes_by_phase[phase_num] = set()
                nodes_by_phase[phase_num].add(node)

    severity_order = {
        "Closed": 0,
        "Skipped": 0,
        "Excluded": 0,
        "Informational": 1,
        "Low": 2,
        "Medium": 3,
        "High": 4,
        "Critical": 5,
    }

    def get_priority(node_name):
        for sev, priority in severity_order.items():
            if sev in node_name:
                return priority
        return 99

    phase_nums = sorted(list(nodes_by_phase.keys()), key=lambda x: int(x))
    dummy_rows = []
    for i in range(len(phase_nums) - 1):
        p1 = phase_nums[i]
        p2 = phase_nums[i + 1]

        sorted_srcs = sorted(list(nodes_by_phase[p1]), key=get_priority)
        sorted_dsts = sorted(list(nodes_by_phase[p2]), key=get_priority)

        max_len = max(len(sorted_srcs), len(sorted_dsts))
        for j in range(max_len):
            src = sorted_srcs[min(j, len(sorted_srcs) - 1)]
            dst = sorted_dsts[min(j, len(sorted_dsts) - 1)]
            dummy_rows.append((src, dst))

    transitions = {}
    for base1, base2 in record_bases:
        state1 = f"{base1} (count: {node_counts[base1]})"
        state2 = f"{base2} (count: {node_counts[base2]})"
        key = f"{state1}::{state2}"
        transitions[key] = transitions.get(key, 0) + 1

    real_rows = []
    for key, weight in transitions.items():
        src, dst = key.split("::")
        real_rows.append([src, dst, weight])

    def sort_key(row):
        return (get_priority(row[0]), get_priority(row[1]))

    sorted_real_rows = sorted(real_rows, key=sort_key)

    final_dummy_rows = []
    for src_base, dst_base in dummy_rows:
        src_name = f"{src_base} (count: {node_counts[src_base]})"
        dst_name = f"{dst_base} (count: {node_counts[dst_base]})"
        final_dummy_rows.append([src_name, dst_name, 0])

    return final_dummy_rows + sorted_real_rows


def render_sidebar(projects_list: list, runs_list: list) -> str:
    """Generates sidebar HTML programmatically with correct relative URLs and test tagging."""
    html = """
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
        <a href="dashboard.html" class="menu-item" id="menu-overview">📊 Overview</a>
        <div class="menu-label">Projects</div>
        <div id="job-menu-list">
    """

    for proj_name, stat in projects_list:
        is_test = proj_name == "tests"
        test_class = " is-test-item" if is_test else ""
        prefix = "🧪 " if is_test else "📁 "
        html += f"""
            <a href="project_{proj_name}.html" class="menu-item{test_class}" id="menu-project-{proj_name}">
                <span>{prefix}{proj_name}</span> <span class="menu-badge">{stat["totalVulns"]}</span>
            </a>
        """

    html += """
        </div>
        <div class="menu-label">Recent Runs</div>
        <div id="recent-runs-menu-list" style="display: flex; flex-direction: column; gap: 4px;">
    """

    for r in runs_list:
        run_id = f"{r['project']}-{r['job_folder']}-{r['run_folder']}"
        is_test = r["project"] == "tests"
        test_class = " is-test-item" if is_test else ""
        short_time = r["timestamp"][5:16]

        html += f"""
            <a href="run_{run_id}.html" class="menu-item{test_class}" id="menu-run-{run_id}" style="font-size: 12px; padding: 6px 10px;">
                <span>⏱️ {r["name"]}</span> 
                <span style="font-size: 10px; color: var(--text-muted); margin-left: auto; padding-left: 8px;">{short_time}</span>
            </a>
        """

    html += """
        </div>
    </nav>
</aside>
    """
    return html


def render_projects_summary_table(projects_list: list) -> str:
    """Pre-renders overview projects summary table rows."""
    html = ""
    for proj_name, stat in projects_list:
        is_test = proj_name == "tests"
        test_class = ' class="is-test-item"' if is_test else ""
        name_display = f"🧪 {proj_name}" if is_test else f"📁 {proj_name}"

        html += f"""
        <tr{test_class}>
            <td><a href="project_{proj_name}.html" class="job-link">{name_display}</a></td>
            <td>{stat["totalRuns"]}</td>
            <td><strong>{stat["totalVulns"]}</strong></td>
            <td style="font-weight: 600; color: var(--critical-color)">{stat["bySeverity"].get("Critical", 0)}</td>
            <td style="font-weight: 600; color: var(--high-color)">{stat["bySeverity"].get("High", 0)}</td>
            <td style="font-weight: 600; color: var(--medium-color)">{stat["bySeverity"].get("Medium", 0)}</td>
            <td style="font-weight: 600; color: var(--low-color)">{stat["bySeverity"].get("Low", 0)}</td>
        </tr>
        """
    return html


def compile_page(
    sidebar_html: str,
    content_html: str,
    page_data: dict,
    active_menu_id: str,
    templates_dir: Path,
) -> str:
    """Compiles page shell with pageData script block and highlights sidebar menu item."""
    template_path = templates_dir / "dashboard.html.tpl"
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    page_data_json = json.dumps(page_data, indent=2)
    html = html.replace("{{page_data_json}}", page_data_json)
    html = html.replace("{{sidebar}}", sidebar_html)
    html = html.replace("{{content}}", content_html)

    active_script = ""
    if active_menu_id:
        active_script = f"""
        <script>
            document.addEventListener("DOMContentLoaded", () => {{
                const activeEl = document.getElementById("{active_menu_id}");
                if (activeEl) activeEl.classList.add("active");
            }});
        </script>
        """
    html = html.replace("</body>", f"{active_script}</body>")

    return html


def generate_dashboard(output_dir: str):
    """Compiles structured static MPA dashboard pages (overview, projects, and runs)."""
    path = Path(output_dir).resolve()
    runs_path = None
    if path.name == "runs":
        runs_path = path
    else:
        for parent in [path] + list(path.parents):
            if parent.name == "runs":
                runs_path = parent
                break
            if (parent / "runs").exists() and (parent / "runs").is_dir():
                runs_path = parent / "runs"
                break

    if not runs_path or not runs_path.exists():
        logger.write(
            f"Error: Could not locate 'runs' directory starting from {output_dir}"
        )
        return

    output_root = runs_path.parent
    logger.write(f"Compiling static MPA dashboard into {output_root}")

    # Gather data
    runs_data = {}
    project_vulns = {}

    for project_dir in sorted(runs_path.iterdir()):
        if not project_dir.is_dir():
            continue

        proj_name = project_dir.name
        project_vulns[proj_name] = []

        for job_dir in sorted(project_dir.iterdir()):
            if not job_dir.is_dir() or job_dir.name == "vulnerabilities":
                continue
            for run_dir in sorted(job_dir.iterdir()):
                if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                    continue

                history_json = run_dir / "vulnerabilities.json"
                metadata_json = run_dir / "metadata.json"

                if not history_json.exists():
                    continue

                try:
                    with open(history_json, "r") as f:
                        history_data = json.load(f)
                    metadata = {}
                    if metadata_json.exists():
                        with open(metadata_json, "r") as f:
                            metadata = json.load(f)

                    open_findings = [
                        v for v in history_data if v.get("status") == "Open"
                    ]
                    report_data = {"vulnerabilities": open_findings}

                    run_id_key = f"{project_dir.name}-{job_dir.name}-{run_dir.name}"
                    runs_data[run_id_key] = format_scan_data(
                        project_dir.name,
                        job_dir.name,
                        run_dir.name,
                        report_data,
                        metadata,
                        history_data,
                    )

                    timestamp = metadata.get("timestamp")
                    formatted_for_project = format_findings(
                        open_findings,
                        run_id_key=run_id_key,
                        timestamp=timestamp,
                        model=metadata.get("model"),
                        run_folder=run_dir.name,
                    )
                    project_vulns[proj_name].extend(formatted_for_project)
                except Exception as e:
                    logger.write(
                        f"Warning: Failed to load findings for run {run_dir.name}: {e}"
                    )

    if not runs_data:
        logger.write("No scan reports found. Local dashboard not compiled.")
        return

    templates_dir = Path(__file__).parent / "templates"

    # Write CSS & JS assets directly to output root
    with open(templates_dir / "dashboard.css", "r", encoding="utf-8") as f:
        with open(output_root / "dashboard.css", "w", encoding="utf-8") as out:
            out.write(f.read())

    with open(templates_dir / "dashboard.js", "r", encoding="utf-8") as f:
        with open(output_root / "dashboard.js", "w", encoding="utf-8") as out:
            out.write(f.read())

    # Pre-compute sidebar listings
    project_stats = compute_project_stats(runs_data)
    projects_list = sorted(list(project_stats.items()))
    runs_list = sorted(
        list(runs_data.values()), key=lambda x: x["timestamp"], reverse=True
    )
    sidebar_html = render_sidebar(projects_list, runs_list)

    # 1. COMPILE GLOBAL OVERVIEW (dashboard.html)
    with open(templates_dir / "view_global.html.tpl", "r", encoding="utf-8") as f:
        global_content = f.read()

    summary_rows = render_projects_summary_table(projects_list)
    global_content = global_content.replace("{{projects_summary_rows}}", summary_rows)

    sankey_all = get_sankey_rows(list(runs_data.values()))
    sankey_no_tests = get_sankey_rows(
        [r for r in runs_data.values() if r["project"] != "tests"]
    )

    global_page_data = {
        "type": "global",
        "sankeyRowsAll": sankey_all,
        "sankeyRowsNoTests": sankey_no_tests,
    }

    html = compile_page(
        sidebar_html, global_content, global_page_data, "menu-overview", templates_dir
    )
    with open(output_root / "dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)

    # 2. COMPILE PROJECTS PAGES (project_[name].html)
    with open(templates_dir / "view_project.html.tpl", "r", encoding="utf-8") as f:
        project_tpl = f.read()

    for proj_name, findings in project_vulns.items():
        proj_content = project_tpl.replace("{{project_name}}", proj_name)

        proj_runs = [r for r in runs_data.values() if r["project"] == proj_name]
        proj_sankey = get_sankey_rows(proj_runs)

        proj_page_data = {
            "type": "project",
            "sankeyRows": proj_sankey,
            "findings": findings,
            "runs": proj_runs,
        }

        html = compile_page(
            sidebar_html,
            proj_content,
            proj_page_data,
            f"menu-project-{proj_name}",
            templates_dir,
        )
        with open(
            output_root / f"project_{proj_name}.html", "w", encoding="utf-8"
        ) as f:
            f.write(html)

    # 3. COMPILE RUNS PAGES (run_[id].html)
    with open(templates_dir / "view_job.html.tpl", "r", encoding="utf-8") as f:
        run_tpl = f.read()

    for run_id, r in runs_data.items():
        run_content = run_tpl
        run_content = run_content.replace("{{job_name}}", r["name"])
        run_content = run_content.replace("{{project_name}}", r["project"])
        run_content = run_content.replace("{{model_name}}", r["model"])
        run_content = run_content.replace("{{commit_hash_short}}", r["commit"][:8])
        run_content = run_content.replace("{{run_folder}}", r["run_folder"])
        run_content = run_content.replace("{{timestamp}}", r["timestamp"])

        run_sankey = get_sankey_rows([r])

        run_page_data = {
            "type": "run",
            "sankeyRows": run_sankey,
            "findings": r["findings"],
        }

        html = compile_page(
            sidebar_html,
            run_content,
            run_page_data,
            f"menu-run-{run_id}",
            templates_dir,
        )
        with open(output_root / f"run_{run_id}.html", "w", encoding="utf-8") as f:
            f.write(html)

    logger.success(f"Dashboard compilation finished successfully.")
