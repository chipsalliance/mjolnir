# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
import os
import sys
import argparse
import tomllib
from sanitize_report import extract_sloppy_toml_blocks
import statistics
import networkx as nx


def load_toml(path):
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def write_toml_cluster(output_path, context, findings):
    """Writes a scoped subset of findings and their context to a TOML file."""
    with open(output_path, "w", encoding="utf-8") as f:
        # Write Context
        f.write("[cluster_context]\n")
        for k, v in context.items():
            if isinstance(v, list):
                vals = ", ".join(f'"{str(x)}"' for x in v)
                f.write(f"{k} = [{vals}]\n")
            else:
                f.write(f'{k} = "{v}"\n')
        f.write("\n")

        # Write Findings
        for finding in findings:
            f.write("[[vulnerabilities]]\n")
            for k, v in finding.items():
                if isinstance(v, str):
                    escaped = (
                        v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                    )
                    f.write(f'{k} = "{escaped}"\n')
                elif isinstance(v, int):
                    f.write(f"{k} = {v}\n")
                elif isinstance(v, list):
                    vals = ", ".join(f'"{str(x).replace('"', '\\"')}"' for x in v)
                    f.write(f"{k} = [{vals}]\n")
            f.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Cluster vulnerabilities using overlapping neighborhood detection."
    )
    parser.add_argument("--report", required=True, help="Raw Phase 1 main_report.toml")
    parser.add_argument("--deps", required=True, help="dependency_graph.toml")
    parser.add_argument(
        "--outdir", required=True, help="Directory to output cluster TOML files"
    )
    parser.add_argument(
        "--max-size", type=int, default=15, help="Max findings per cluster"
    )
    args = parser.parse_args()

    with open(args.report, "r") as f:
        raw_report_text = f.read()

    all_findings = extract_sloppy_toml_blocks(raw_report_text)

    os.makedirs(args.outdir, exist_ok=True)

    deps_data = load_toml(args.deps).get("dependencies", {})

    if not all_findings:
        print("No findings to cluster. Exiting.")
        return

    # Build dependency graph
    G = nx.Graph()
    for src, targets in deps_data.items():
        for t in targets:
            G.add_edge(src, t)

    hubs = []

    # Resolve short filenames to full graph paths
    # The agent often halucinates the filenames without the path
    valid_files = set(G.nodes)
    for finding in all_findings:
        f_path = finding.get("file", "")
        # If the exact path isn't in the graph, try to find a suffix match
        if f_path not in valid_files and f_path != "":
            for vf in valid_files:
                if vf.endswith(f_path) or f_path in vf:
                    finding["file"] = vf
                    break

    # Automatic hub pruning
    if len(G.nodes) > 1:
        degrees = [deg for _, deg in G.degree()]
        mean_deg = statistics.mean(degrees)
        stdev_deg = statistics.stdev(degrees) if len(degrees) > 1 else 0

        # Define a hub as 3 standard deviations above mean, with a minimum floor
        threshold = max(mean_deg + (3 * stdev_deg), 10)
        hubs = [node for node, deg in G.degree() if deg > threshold]

        if hubs:
            print(
                f"Pruning {len(hubs)} high-degree utility hubs from neighborhood expansions..."
            )
            G.remove_nodes_from(hubs)

    # Strict 1-hop merge
    grouped_findings = {}

    vulnerable_files = list({f.get("file", "unknown") for f in all_findings})
    valid_vuln_files = [f for f in vulnerable_files if f in G]

    # Build a "Proximity Graph" of only the vulnerable files
    ProximityGraph = nx.Graph()
    ProximityGraph.add_nodes_from(valid_vuln_files)

    for i in range(len(valid_vuln_files)):
        for j in range(i + 1, len(valid_vuln_files)):
            file_a = valid_vuln_files[i]
            file_b = valid_vuln_files[j]
            # Only merge if they directly interact
            if G.has_edge(file_a, file_b):
                ProximityGraph.add_edge(file_a, file_b)

    # Extract the merged components
    merged_components = list(nx.connected_components(ProximityGraph))

    # Add isolated files that weren't in the graph
    isolated_files = [f for f in vulnerable_files if f not in G]
    for iso in isolated_files:
        merged_components.append({iso})

    # Build the final overlapping contexts
    for idx, core_files in enumerate(merged_components):
        neighborhood = set()

        # The context is the 1-hop ego graph to provide just enough surrounding code
        for f in core_files:
            if f in G:
                ego_net = nx.ego_graph(G, f, radius=1)
                neighborhood.update(ego_net.nodes)
            else:
                neighborhood.add(f)

        # Name the cluster based on the first file alphabetically
        primary_file = sorted(list(core_files))[0]
        safe_name = os.path.basename(primary_file).replace(".", "_")
        group_id = f"ThreatZone_{safe_name}_{idx}"

        # Pull all findings that belong to ANY file in this expanded neighborhood
        relevant_findings = [
            f for f in all_findings if f.get("file", "unknown") in neighborhood
        ]

        grouped_findings[group_id] = relevant_findings

    print(
        f"Consolidated {len(vulnerable_files)} vulnerable files into {len(merged_components)} threat zones."
    )

    # Size enforcement & file writing
    cluster_count = 0
    for group_id, group_findings in grouped_findings.items():
        # Split logic for large groups
        chunks = [
            group_findings[i : i + args.max_size]
            for i in range(0, len(group_findings), args.max_size)
        ]

        for i, chunk in enumerate(chunks):
            # Extract distinct files involved in this chunk to provide agent context
            involved_files = list({f.get("file") for f in chunk if f.get("file")})

            context = {
                "cluster_id": f"{group_id}_part{i + 1}"
                if len(chunks) > 1
                else group_id,
                "architectural_type": group_id.split("_")[0],
                "files_in_scope": involved_files,
            }

            out_path = os.path.join(args.outdir, f"cluster_{cluster_count:04d}.toml")
            write_toml_cluster(out_path, context, chunk)
            cluster_count += 1

    print(
        f"Successfully chunked {len(all_findings)} findings into {cluster_count} context-bounded clusters."
    )


if __name__ == "__main__":
    main()
