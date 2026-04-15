"""Domain extraction — identify business domains and flows from knowledge graph."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
from .llm import _llm_request, _extract_json


def extract_domains(graph_data: dict, llm_url: str = "", model: str = "") -> dict:
    """Extract business domains from graph. LLM optional for flow naming."""
    nodes = graph_data["nodes"]
    edges = graph_data["edges"]

    # Group nodes by domain_hint
    domains = defaultdict(list)
    for n in nodes:
        hint = (n.get("semantics", {}).get("domain_hint", "") or n.get("domain", ""))
        if hint and n["type"] in ("function", "class"):
            domains[hint].append(n)

    result = {"domains": []}
    for domain_name, domain_nodes in sorted(domains.items(), key=lambda x: -len(x[1])):
        # Find entry points → trace call chains for flows
        entries = [n for n in domain_nodes
                   if (n.get("semantics", {}).get("execution_role", "") or n.get("role", "")) == "entry_point"]
        if not entries:
            entries = domain_nodes[:3]  # fallback: top nodes

        flows = _trace_flows(entries, edges, {n["id"]: n for n in nodes})

        domain = {
            "name": domain_name,
            "node_count": len(domain_nodes),
            "key_nodes": [n["name"] for n in domain_nodes[:10]],
            "flows": flows,
        }

        # LLM: enrich domain description
        if llm_url and flows:
            desc = _enrich_domain(domain, llm_url, model)
            if desc: domain["description"] = desc

        result["domains"].append(domain)

    return result


def _trace_flows(entries: list, edges: list, node_map: dict) -> list:
    """Trace call chains from entry points to build flows."""
    flows = []
    calls_from = defaultdict(list)
    for e in edges:
        if e["type"] == "calls": calls_from[e["source"]].append(e["target"])

    for entry in entries[:5]:
        chain = []
        visited = set()
        _walk_chain(entry["id"], calls_from, node_map, chain, visited, max_depth=6)
        if len(chain) >= 2:
            flows.append({
                "entry": entry["name"],
                "steps": [{"name": node_map[nid]["name"], "file": node_map[nid].get("file_path", "")}
                          for nid in chain if nid in node_map],
            })
    return flows[:5]


def _walk_chain(nid, calls_from, node_map, chain, visited, max_depth):
    if nid in visited or len(chain) >= max_depth: return
    visited.add(nid)
    chain.append(nid)
    for target in calls_from.get(nid, [])[:3]:
        if target in node_map and target not in visited:
            _walk_chain(target, calls_from, node_map, chain, visited, max_depth)


def _enrich_domain(domain: dict, llm_url: str, model: str) -> Optional[str]:
    prompt = (
        f"Describe this business domain in 1-2 sentences.\n"
        f"Domain: {domain['name']}\n"
        f"Key components: {', '.join(domain['key_nodes'][:8])}\n"
        f"Flows: {len(domain['flows'])}\n"
    )
    try:
        return _llm_request(llm_url, model, prompt).strip().strip('"')
    except Exception:
        return None


def format_domains(result: dict) -> str:
    lines = []
    for d in result["domains"]:
        lines.append(f"\n  {d['name'].upper()} ({d['node_count']} nodes)")
        if d.get("description"): lines.append(f"    {d['description']}")
        lines.append(f"    Key: {', '.join(d['key_nodes'][:6])}")
        for f in d.get("flows", []):
            steps = " → ".join(s["name"] for s in f["steps"])
            lines.append(f"    Flow: {steps}")
    return "\n".join(lines)
