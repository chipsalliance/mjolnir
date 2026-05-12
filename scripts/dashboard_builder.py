# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import logging
from pathlib import Path
import tomllib

FILENAME_MAPPINGS = {
    "dashboard.html": ("Interactive Dashboard", "bg-html", "HTML"),
    "main_report.md": ("Main Vulnerability Report", "bg-md", "MD"),
    "main_report.toml": ("Main Vulnerability Report", "bg-toml", "TOML"),
    "reviewed_report.md": (
        "Agent Filtered Vulnerability Report",
        "bg-md",
        "MD",
    ),
}

CARD_TEMPLATE = """
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title">{display_name}</h5>
                    <div class="scan-info">📂 <code>{scan_dir}</code></div>
                    <div class="list-group">
                        {links_html}
                    </div>
                </div>
            </div>
"""


def load_components(config_paths):
    """Loads and merges components from multiple TOML files."""
    components = {}
    for path_str in config_paths:
        path = Path(path_str)
        if not path.exists():
            logging.error(f"Components config file not found: {path}")
            continue
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
                components.update(data)
        except Exception as e:
            logging.error(f"Failed to parse components file {path}: {e}")
    return components


def get_assets(dashboards_dir):
    """Reads CSS and template assets from dashboards directory."""
    shared_css_path = dashboards_dir / "dashboard.css"
    mjolnir_css_path = dashboards_dir / "mjolnir_dashboard.css"
    template_path = dashboards_dir / "mjolnir_dashboard.html.tpl"

    if not template_path.exists():
        logging.error(f"Template not found: {template_path}")
        return None, None, None

    with open(shared_css_path, "r") as f:
        shared_css = f.read()
    with open(mjolnir_css_path, "r") as f:
        mjolnir_css = f.read()
    with open(template_path, "r") as f:
        html_template = f.read()

    return shared_css, mjolnir_css, html_template


def generate_link_html(filename, url):
    """Generates HTML link for a report file."""
    mapping = FILENAME_MAPPINGS.get(filename)
    if mapping:
        link_text, badge_class, badge_text = mapping
        badge_html = f'<span class="badge {badge_class}">{badge_text}</span>'
    else:
        link_text = filename
        badge_html = ""

    return f'<a href="{url}" class="list-group-item">{link_text}{badge_html}</a>\n'


def generate_card_html(display_name, scan_dir, links_html):
    """Generates HTML for a component card."""
    return CARD_TEMPLATE.format(
        display_name=display_name, scan_dir=scan_dir, links_html=links_html
    )


def build_dashboard(html_template, shared_css, mjolnir_css, cards_html):
    """Builds the final dashboard HTML content."""
    content = html_template.replace("{{dashboard_css}}", shared_css)
    content = content.replace("{{mjolnir_css}}", mjolnir_css)
    content = content.replace("{{cards_html}}", cards_html)
    return content
