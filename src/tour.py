"""Guided tour generator — learning path ordered by dependency."""

from collections import defaultdict
from pathlib import Path
from typing import List, Optional


LAYER_ORDER = ["Data / Storage", "Infrastructure", "Service / Logic", "API / Routes", "UI / Frontend", "Tests", "Documentation"]


def generate_tour(graph_data: dict, focus_domain: str = None) -> List[dict]:
    """Generate tour stops ordered by layer dependency."""
    nodes = graph_data["nodes"]
    layers = graph_data.get("layers", [])
    edges = graph_data["edges"]

    # Build layer lookup
    node_layer = {}
    for l in layers:
        for nid in l["node_ids"]: node_layer[nid] = l["name"]

    # Filter by domain if specified
    if focus_domain:
        domain_ids = {n["id"] for n in nodes
                      if (n.get("semantics", {}).get("domain_hint", "") or n.get("domain", "")) == focus_domain}
        nodes = [n for n in nodes if n["id"] in domain_ids]

    # Group file nodes by layer, then by directory
    layer_dirs = defaultdict(lambda: defaultdict(list))
    for n in nodes:
        if n["type"] != "file": continue
        layer = node_layer.get(n["id"], "Service / Logic")
        dir_path = str(Path(n.get("file_path", "")).parent)
        layer_dirs[layer][dir_path].append(n)

    # Build stops in layer dependency order
    stops = []
    for layer_name in LAYER_ORDER:
        dirs = layer_dirs.get(layer_name, {})
        if not dirs: continue
        # Sort dirs by file count (most files first)
        for dir_path, dir_files in sorted(dirs.items(), key=lambda x: -len(x[1])):
            if len(dir_files) < 1: continue
            # Find complex/important nodes in this dir
            key_files = sorted(dir_files, key=lambda n: (
                0 if n.get("complexity") == "complex" else 1, -len(n.get("summary", ""))), )[:5]
            stops.append({
                "layer": layer_name,
                "directory": dir_path,
                "file_count": len(dir_files),
                "key_files": [n["name"] for n in key_files],
            })

    return stops


def format_tour(stops: List[dict], project_name: str = "") -> str:
    lines = [f"\n  {project_name} — Guided Tour\n"]
    for i, stop in enumerate(stops, 1):
        lines.append(f"  Stop {i}/{len(stops)}: {stop['layer']} ({stop['directory']}/)")
        lines.append(f"    {stop['file_count']} files — Key: {', '.join(stop['key_files'][:4])}")
        if i < len(stops):
            lines.append("")
    return "\n".join(lines)
