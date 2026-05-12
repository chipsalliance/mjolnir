# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env python3
"""Aggregates vulnerability scan results and generates a landing page."""

import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tomllib

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

FILENAME_MAPPINGS = {
    "dashboard.html": ("Interactive Dashboard", "bg-html", "HTML"),
    "main_report.md": ("Main Vulnerability Report", "bg-md", "MD"),
    "main_report.toml": ("Main Vulnerability Report", "bg-toml", "TOML"),
    "reviewed_report.md": ("Agent Filtered Vulnerability Report", "bg-md", "MD"),
}


def load_components(config_paths):
    """Loads and merges components from multiple TOML files."""
    components = {}
    for path_str in config_paths:
        path = Path(path_str)
        if not path.exists():
            logging.error(f"Components config file not found: {path}")
            sys.exit(1)
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
                components.update(data)
        except Exception as e:
            logging.error(f"Failed to parse components file {path}: {e}")
            sys.exit(1)
    return components


def resolve_default_components():
    """Finds default components.toml in standard locations relative to CWD."""
    cwd = Path.cwd()
    possible_paths = [
        cwd / "mjolnir" / "scripts" / "components.toml",
        cwd / "scripts" / "components.toml",
        cwd / "components.toml",
    ]
    for path in possible_paths:
        if path.exists():
            return path
    return None


def resolve_dashboards_dir(cli_path):
    """Finds dashboards directory in standard locations relative to CWD or uses CLI path."""
    if cli_path:
        path = Path(cli_path).resolve()
        if path.exists():
            return path
        logging.error(f"Specified dashboards directory not found: {path}")
        sys.exit(1)

    cwd = Path.cwd()
    possible_paths = [
        cwd / "mjolnir" / "dashboards",
        cwd / "dashboards",
    ]
    for path in possible_paths:
        if path.exists():
            return path

    logging.error(
        "Could not find dashboards directory in standard locations. Please specify it using --dashboards-dir."
    )
    sys.exit(1)


FILES_TO_COPY = [
    "dashboard.html",
    "reviewed_report.md",
]

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


def find_latest_scan(component_dir: Path) -> Path:
    """Finds the latest scan directory in the given component directory.

    Supports run_gemini_* prefixes and sorts by the YYYYMMDD_HHMMSS
    timestamp at the end of the directory name.
    """
    if not component_dir.exists():
        logging.warning(f"Component directory does not exist: {component_dir}")
        return None

    run_dirs = [
        d for d in component_dir.iterdir() if d.is_dir() and d.name.startswith("run_")
    ]
    if not run_dirs:
        logging.warning(f"No scan directories found in: {component_dir}")
        return None

    def get_timestamp(path):
        parts = path.name.split("_")
        if len(parts) >= 3:
            if (
                len(parts[-2]) == 8
                and parts[-2].isdigit()
                and len(parts[-1]) == 6
                and parts[-1].isdigit()
            ):
                return f"{parts[-2]}_{parts[-1]}"
            for i in range(len(parts) - 1):
                if (
                    len(parts[i]) == 8
                    and parts[i].isdigit()
                    and len(parts[i + 1]) == 6
                    and parts[i + 1].isdigit()
                ):
                    return f"{parts[i]}_{parts[i + 1]}"
        logging.warning(f"Could not parse timestamp from name: {path.name}")
        return path.name

    run_dirs.sort(key=get_timestamp)
    return run_dirs[-1]


def generate_link_html(comp_key: str, filename: str) -> str:
    """Generates HTML link for a report file."""
    relative_link = f"{comp_key}/{filename}"

    mapping = FILENAME_MAPPINGS.get(filename)
    if mapping:
        link_text, badge_class, badge_text = mapping
        badge_html = f'<span class="badge {badge_class}">{badge_text}</span>'
    else:
        link_text = filename
        badge_html = ""

    return f'<a href="{relative_link}" class="list-group-item">{link_text}{badge_html}</a>\n'


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate vulnerability scan results."
    )
    parser.add_argument("target_dir", type=str, help="Directory to copy results to.")
    default_components = resolve_default_components()
    parser.add_argument(
        "--components",
        action="append",
        default=[str(default_components)] if default_components else [],
        help="Path to TOML file containing component definitions. Can be specified multiple times.",
    )
    parser.add_argument(
        "--dashboards-dir",
        help="Path to the dashboards directory containing templates and CSS assets.",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        nargs="+",
        help="Restricts aggregation to the specified jobs (components).",
    )
    parser.add_argument(
        "--regen-html",
        action="store_true",
        help="Only regenerate the index.html landing page from existing results in the target directory, without copying new files.",
    )
    args = parser.parse_args()

    if not args.components:
        parser.error(
            "No components file specified and default components.toml not found in standard locations."
        )
    components = load_components(args.components)

    if args.jobs:
        invalid_jobs = [j for j in args.jobs if j not in components]
        if invalid_jobs:
            parser.error(
                f"Invalid jobs specified: {invalid_jobs}. Available choices: {list(components.keys())}"
            )

    target_base = Path(args.target_dir).resolve()
    output_base = Path.cwd()
    dashboards_dir = resolve_dashboards_dir(args.dashboards_dir)

    # Paths to assets
    shared_css_path = dashboards_dir / "dashboard.css"
    mjolnir_css_path = dashboards_dir / "mjolnir_dashboard.css"
    template_path = dashboards_dir / "mjolnir_dashboard.html.tpl"

    logging.info(f"Dashboards directory: {dashboards_dir}")
    logging.info(f"Target directory: {target_base}")

    # Read assets
    assets_exist = True
    for p in [shared_css_path, mjolnir_css_path, template_path]:
        if not p.exists():
            logging.error(f"Required asset not found: {p}")
            assets_exist = False

    if not assets_exist:
        logging.error("Cannot proceed due to missing assets.")
        return

    with open(shared_css_path, "r", encoding="utf-8") as f:
        shared_css = f.read()
    with open(mjolnir_css_path, "r", encoding="utf-8") as f:
        mjolnir_css = f.read()
    with open(template_path, "r", encoding="utf-8") as f:
        html_template = f.read()

    cards_html = ""

    jobs_to_process = args.jobs if args.jobs else list(components.keys())

    for comp_key, comp_info in components.items():
        display_name = comp_info["display_name"]
        comp_target_dir = target_base / comp_key

        if comp_key in jobs_to_process and not args.regen_html:
            source_dir_name = comp_info["source_dir"]
            source_path = output_base / source_dir_name
            if not source_path.exists():
                # Try parent (if mjolnir is a subdirectory of custom extension repo)
                parent_path = output_base.parent / source_dir_name
                if parent_path.exists():
                    source_path = parent_path

            logging.info(f"Processing {display_name}...")

            latest_scan_path = find_latest_scan(source_path)
            if not latest_scan_path:
                logging.warning(f"Skipping {display_name} due to missing scan data.")
                continue

            logging.info(f"Found latest scan: {latest_scan_path.name}")

            comp_target_dir.mkdir(parents=True, exist_ok=True)

            # Write metadata
            scan_info_file = comp_target_dir / "scan_info.json"
            try:
                with open(scan_info_file, "w", encoding="utf-8") as f:
                    json.dump({"scan_dir": latest_scan_path.name}, f, indent=2)
            except Exception as e:
                logging.error(f"Failed to write scan info for {comp_key}: {e}")

            links_html = ""
            copied_files_count = 0

            # Dynamically determine which main report to copy
            main_report = None
            if (latest_scan_path / "main_report.toml").exists():
                main_report = "main_report.toml"
            elif (latest_scan_path / "main_report.md").exists():
                main_report = "main_report.md"
            else:
                logging.info(
                    f"No main report (TOML or MD) found in {latest_scan_path.name}"
                )

            # Build dynamic list of files to copy
            files_to_copy = list(FILES_TO_COPY)
            if main_report:
                files_to_copy.append(main_report)

            for filename in files_to_copy:
                src_file = latest_scan_path / filename
                if src_file.exists():
                    dst_file = comp_target_dir / filename
                    shutil.copy2(src_file, dst_file)
                    copied_files_count += 1
                    links_html += generate_link_html(comp_key, filename)
                else:
                    logging.info(
                        f"File {filename} not found in {latest_scan_path.name}"
                    )

            if copied_files_count > 0:
                cards_html += CARD_TEMPLATE.format(
                    display_name=display_name,
                    scan_dir=latest_scan_path.name,
                    links_html=links_html,
                )
            else:
                logging.warning(f"No files copied for {display_name}, skipping card.")
        else:
            # Preserve existing
            scan_info_file = comp_target_dir / "scan_info.json"
            if scan_info_file.exists() and comp_target_dir.exists():
                logging.info(f"Preserving existing results for {display_name}...")
                try:
                    with open(scan_info_file, "r", encoding="utf-8") as f:
                        info = json.load(f)
                        scan_dir = info.get("scan_dir", "Unknown Scan")
                except Exception as e:
                    logging.warning(f"Failed to read scan info for {comp_key}: {e}")
                    scan_dir = "Existing Scan"

                links_html = ""
                existing_files_count = 0
                possible_files = list(FILES_TO_COPY) + [
                    "main_report.toml",
                    "main_report.md",
                ]
                for filename in possible_files:
                    dst_file = comp_target_dir / filename
                    if dst_file.exists():
                        existing_files_count += 1
                        links_html += generate_link_html(comp_key, filename)

                if existing_files_count > 0:
                    cards_html += CARD_TEMPLATE.format(
                        display_name=display_name,
                        scan_dir=scan_dir,
                        links_html=links_html,
                    )
                else:
                    logging.warning(
                        f"No existing files found for {display_name} despite scan_info.json presence."
                    )
            else:
                logging.info(f"No existing results to preserve for {display_name}.")

    if cards_html:
        # Perform triple injection using .replace()
        index_html_content = html_template.replace("{{dashboard_css}}", shared_css)
        index_html_content = index_html_content.replace("{{mjolnir_css}}", mjolnir_css)
        index_html_content = index_html_content.replace("{{cards_html}}", cards_html)

        index_path = target_base / "index.html"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_html_content)
        logging.info(f"Generated landing page at: {index_path}")
    else:
        logging.error("No results aggregated, index.html not generated.")


if __name__ == "__main__":
    main()
