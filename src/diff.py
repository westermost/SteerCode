"""Diff analysis — map git changes to knowledge graph impact."""

import subprocess
from pathlib import Path
from typing import List, Dict, Set, Optional


def get_changed_files(root: Path, ref: str = None) -> List[str]:
    """Get changed files from git. ref=None → staged+unstaged, ref='HEAD~3' → last 3 commits."""
    try:
        if ref:
            out = subprocess.check_output(["git", "diff", "--name-only", ref], cwd=str(root), text=True, stderr=subprocess.DEVNULL)
        else:
            staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=str(root), text=True, stderr=subprocess.DEVNULL)
            unstaged = subprocess.check_output(["git", "diff", "--name-only"], cwd=str(root), text=True, stderr=subprocess.DEVNULL)
            out = staged + unstaged
        return sorted(set(f.strip() for f in out.splitlines() if f.strip()))
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def analyze_diff(graph_data: dict, changed_files: List[str]) -> dict:
    """Map changed files to graph nodes, expand 1-hop, compute risk."""
    nodes = {n["id"]: n for n in graph_data["nodes"]}
    edges = graph_data["edges"]

    # Map file paths → node IDs
    path_to_id = {}
    for n in graph_data["nodes"]:
        if n.get("file_path"):
            path_to_id[n["file_path"]] = n["id"]

    # Find changed nodes (files + their contained functions/classes)
    changed_ids = set()
    for fp in changed_files:
        fid = path_to_id.get(fp)
        if fid:
            changed_ids.add(fid)
            for e in edges:
                if e["source"] == fid and e["type"] == "contains":
                    changed_ids.add(e["target"])

    # Expand 1-hop via calls/imports
    affected_ids = set()
    for cid in changed_ids:
        for e in edges:
            if e["type"] not in ("calls", "imports"): continue
            nb = e["target"] if e["source"] == cid else (e["source"] if e["target"] == cid else None)
            if nb and nb not in changed_ids:
                affected_ids.add(nb)

    # Collect layers
    affected_layers = set()
    for l in graph_data.get("layers", []):
        for nid in l["node_ids"]:
            if nid in changed_ids or nid in affected_ids:
                affected_layers.add(l["name"])

    # Risk scoring
    changed_nodes = [nodes[nid] for nid in changed_ids if nid in nodes]
    risk = _compute_risk(changed_nodes)

    # Unmapped files
    unmapped = [fp for fp in changed_files if fp not in path_to_id]

    return {
        "changed_files": changed_files,
        "changed": [_node_summary(nodes[nid]) for nid in changed_ids if nid in nodes and nodes[nid]["type"] != "file"],
        "affected": [_node_summary(nodes[nid]) for nid in affected_ids if nid in nodes],
        "layers": sorted(affected_layers),
        "risk": risk,
        "unmapped": unmapped,
    }


def _compute_risk(changed_nodes: list) -> str:
    for n in changed_nodes:
        sem = n.get("semantics", {})
        role = sem.get("execution_role", "") or n.get("role", "")
        effects = [e.get("type", e) if isinstance(e, dict) else e for e in (sem.get("side_effects", []) or n.get("effects", []))]
        if role == "orchestrator" or any("external_api" in str(e) for e in effects):
            return "HIGH"
        if role in ("entry_point", "data_access") or any("db_write" in str(e) for e in effects):
            return "MEDIUM"
    return "LOW"


def _node_summary(n: dict) -> dict:
    sem = n.get("semantics", {})
    return {
        "name": n["name"], "type": n["type"], "file": n.get("file_path", ""),
        "domain": sem.get("domain_hint", "") or n.get("domain", ""),
        "role": sem.get("execution_role", "") or n.get("role", ""),
        "effects": [e.get("type", e) if isinstance(e, dict) else e for e in (sem.get("side_effects", []) or n.get("effects", []))],
    }


def format_diff(result: dict) -> str:
    """Format diff analysis for terminal output."""
    lines = []
    risk_color = {"HIGH": "\033[31m", "MEDIUM": "\033[33m", "LOW": "\033[32m"}
    rc = risk_color.get(result["risk"], "")

    lines.append(f"  Changed: {len(result['changed_files'])} files, {len(result['changed'])} functions/classes")
    lines.append(f"  Affected: {len(result['affected'])} nodes across {len(result['layers'])} layers ({', '.join(result['layers'])})")
    lines.append(f"  Risk: {rc}{result['risk']}\033[0m")
    lines.append("")

    if result["changed"]:
        lines.append("  Changed:")
        for n in result["changed"][:20]:
            extra = []
            if n["role"]: extra.append(n["role"])
            if n["domain"]: extra.append(f"[{n['domain']}]")
            if n["effects"]: extra.append("→ " + ", ".join(n["effects"][:3]))
            lines.append(f"    ✎ {n['name']} ({n['type']}) {' · '.join(extra)}")

    if result["affected"]:
        lines.append("\n  Affected (1-hop):")
        for n in result["affected"][:20]:
            lines.append(f"    → {n['name']} ({n['type']}) in {n['file']}")

    if result["unmapped"]:
        lines.append(f"\n  Unmapped: {', '.join(result['unmapped'][:5])}")

    return "\n".join(lines)
