"""Dashboard HTML generation."""

import json
from pathlib import Path


def _strip_defaults(graph_data: dict) -> dict:
    """Remove empty/default fields to reduce JSON size."""
    stripped = {**graph_data}
    stripped["nodes"] = []
    for n in graph_data["nodes"]:
        node = {k: v for k, v in n.items()
                if v and v != [] and v != (0, 0) and v != [0, 0] and v != "simple" and k != "semantics"}
        if n.get("complexity") and n["complexity"] != "simple":
            node["complexity"] = n["complexity"]
        # Include semantic fields inline for dashboard
        sem = n.get("semantics", {})
        if sem:
            if sem.get("domain_hint"): node["domain"] = sem["domain_hint"]
            if sem.get("execution_role"): node["role"] = sem["execution_role"]
            if sem.get("side_effects"):
                node["effects"] = [e["type"] for e in sem["side_effects"]]
            if sem.get("control_flow"):
                node["control_flow"] = sem["control_flow"]
            if sem.get("importance"): node["importance"] = sem["importance"]
        stripped["nodes"].append(node)
    stripped["edges"] = []
    for e in graph_data["edges"]:
        edge = {"source": e["source"], "target": e["target"], "type": e["type"]}
        if e.get("weight", 0.5) != 0.5: edge["weight"] = e["weight"]
        stripped["edges"].append(edge)
    return stripped


def _build_compact_graph(graph_data: dict) -> dict:
    """Build a compact graph for AI steering — columnar format, full quality, split by layer."""
    nodes = graph_data["nodes"]
    edges = graph_data["edges"]

    # Path dedup: index paths, strip common prefix
    all_paths = sorted(set(n.get("file_path", "") for n in nodes if n.get("file_path")))
    if len(all_paths) > 1:
        from os.path import commonprefix
        prefix = commonprefix(all_paths)
        prefix = prefix[:prefix.rfind("/") + 1] if "/" in prefix else ""
    else:
        prefix = ""
    trimmed = [p[len(prefix):] for p in all_paths]
    path_idx = {p: i for i, p in enumerate(all_paths)}

    # Build node ID → path index + name for edge resolution
    id_map = {}  # id → (path_idx, name)
    for n in nodes:
        if n.get("name"):
            id_map[n["id"]] = (path_idx.get(n.get("file_path", ""), 0), n["name"])

    # Columnar format per node: [path_idx, type_char, name, line_start, summary, complexity_char]
    # type: F=file f=function C=class | complexity: !=complex ~=moderate (omit if simple)
    type_map = {"file": "F", "function": "f", "class": "C"}
    comp_map = {"complex": "!", "moderate": "~"}

    def _compact_node(n):
        entry = [
            path_idx.get(n.get("file_path", ""), 0),
            type_map.get(n["type"], "?"),
            n.get("name", ""),
        ]
        lr = n.get("line_range", [0, 0])
        if lr and lr[0]: entry.append(lr[0])
        else: entry.append(0)
        s = str(n.get("summary", ""))
        entry.append(s if s else "")
        c = comp_map.get(n.get("complexity"), "")
        if c: entry.append(c)
        return entry

    # Build layer → node index mapping
    node_layer = {}
    for l in graph_data["layers"]:
        for nid in l["node_ids"]:
            node_layer[nid] = l["id"]

    return {
        "_prefix": prefix,
        "paths": trimmed,
        "nodes": [_compact_node(n) for n in nodes if n.get("name")],
        "edges": [[id_map[e["source"]][1], id_map[e["target"]][1], e["type"][0]]
                   for e in edges if e["source"] in id_map and e["target"] in id_map],
        "layers": {l["name"]: len(l["node_ids"]) for l in graph_data["layers"]},
        "project": graph_data["project"],
        "_": "nodes:[path_idx,F/f/C,name,line,summary,!/~] edges:[src,tgt,i/c/>/^]",
    }


def generate_dashboard(graph_data: dict, output_dir: Path):
    dashboard_dir = Path(__file__).parent.parent.parent / "dashboard"
    template = (dashboard_dir / "template.html").read_text(encoding="utf-8")
    css = (dashboard_dir / "style.css").read_text(encoding="utf-8")
    js = (dashboard_dir / "app.js").read_text(encoding="utf-8")
    i18n = (dashboard_dir / "i18n.js").read_text(encoding="utf-8")

    output_dir.mkdir(parents=True, exist_ok=True)

    compact = _strip_defaults(graph_data)

    kg_path = output_dir / "knowledge-graph.json"
    kg_path.write_text(json.dumps(compact, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Compact version for AI steering (much smaller)
    compact_ai = _build_compact_graph(graph_data)
    kg_compact_path = output_dir / "knowledge-graph.compact.json"
    kg_compact_path.write_text(json.dumps(compact_ai, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Progressive disclosure: split by layer for agentic loading
    _build_layer_files(graph_data, output_dir)

    graph_json = json.dumps(graph_data, ensure_ascii=False, separators=(",", ":"))
    (output_dir / "data.js").write_text(f"const GRAPH_DATA={graph_json};", encoding="utf-8")

    html = template.replace("{{CSS}}", css).replace("{{I18N}}", i18n).replace("{{JS}}", js)
    html = html.replace("{{PROJECT_NAME}}", graph_data["project"]["name"])
    dash_path = output_dir / "dashboard.html"
    dash_path.write_text(html, encoding="utf-8")

    return dash_path, kg_path


def _write_layer_chunk(layers_dir, fname_base, layer_name, layer_nodes, layer_edges,
                       id_to_name, _is_default_summary, index):
    """Write a single layer chunk file."""
    layer_paths = sorted(set(n.get("file_path", "") for n in layer_nodes))
    path_idx = {p: i for i, p in enumerate(layer_paths)}
    type_map = {"file": "F", "function": "f", "class": "C"}

    compact_nodes = []
    for n in layer_nodes:
        s = str(n.get("summary", ""))
        entry = [path_idx.get(n.get("file_path", ""), 0), type_map.get(n["type"], "?"),
                 n.get("name", ""), "" if _is_default_summary(s) else s]
        c = n.get("complexity", "simple")
        if c != "simple":
            entry.append("!" if c == "complex" else "~")
        compact_nodes.append(entry)

    compact_edges = [[id_to_name.get(e["source"], ""), id_to_name.get(e["target"], ""), e["type"][0]]
                     for e in layer_edges]

    layer_data = {
        "layer": layer_name, "paths": layer_paths,
        "_": "nodes:[path_idx,F/f/C,name,summary,!/~] edges:[src,tgt,type]",
        "nodes": compact_nodes, "edges": compact_edges,
    }

    fname = f"{fname_base}.json"
    (layers_dir / fname).write_text(
        json.dumps(layer_data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    fsize = (layers_dir / fname).stat().st_size
    index["layers"][layer_name] = {
        "file": f"layers/{fname}", "nodes": len(layer_nodes),
        "edges": len(compact_edges), "size_kb": round(fsize / 1024), "est_tokens": round(fsize / 4),
    }


def _build_layer_files(graph_data: dict, output_dir: Path):
    """Split knowledge graph into per-layer files for progressive AI loading.
    Recursively chunks large layers by directory depth until each fits in context."""
    layers_dir = output_dir / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)

    nodes = graph_data["nodes"]
    edges = graph_data["edges"]

    node_to_layer = {}
    for l in graph_data["layers"]:
        for nid in l["node_ids"]:
            node_to_layer[nid] = l["id"]

    node_map = {n["id"]: n for n in nodes}
    id_to_name = {n["id"]: n.get("name", n["id"]) for n in nodes}

    def _is_default_summary(s):
        return not s or s.startswith("Function") or s.startswith("Class with") or ("file (" in s and "lines)" in s)

    MAX_CHUNK_TOKENS = 200_000

    def _est_tokens(node_list):
        return sum(len(n.get("file_path", "")) + len(str(n.get("summary", ""))) + 30 for n in node_list) // 4

    def _split_by_path_depth(node_list, depth):
        """Group nodes by path component at given depth."""
        from collections import defaultdict
        groups = defaultdict(list)
        for n in node_list:
            parts = n.get("file_path", "").split("/")
            key = "/".join(parts[:depth + 1]) if len(parts) > depth else "/".join(parts) or "_root"
            groups[key].append(n)
        return groups

    def _chunk_recursive(layer_name, lid, node_list, chunk_counter, depth=1):
        """Recursively split until each chunk fits in MAX_CHUNK_TOKENS."""
        if not node_list:
            return
        if _est_tokens(node_list) <= MAX_CHUNK_TOKENS or len(node_list) <= 100 or depth > 6:
            chunk_counter[0] += 1
            node_ids = {n["id"] for n in node_list}
            _write_layer_chunk(
                layers_dir, f"{lid}_{chunk_counter[0]}" if chunk_counter[0] > 0 else lid,
                layer_name, node_list,
                [e for e in edges if e["source"] in node_ids and e["target"] in node_ids],
                id_to_name, _is_default_summary, index)
            return

        groups = _split_by_path_depth(node_list, depth)
        if len(groups) <= 1:
            _chunk_recursive(layer_name, lid, node_list, chunk_counter, depth + 1)
            return

        # Merge tiny groups (≤20 nodes) to avoid chunk explosion
        merged = []
        for group_path, group_nodes in sorted(groups.items(), key=lambda x: -len(x[1])):
            if len(group_nodes) <= 20:
                merged.extend(group_nodes)
            else:
                short = group_path.split("/")[-1] or group_path
                _chunk_recursive(f"{layer_name} ({short})", lid, group_nodes, chunk_counter, depth + 1)
        if merged:
            _chunk_recursive(layer_name, lid, merged, chunk_counter, depth + 1)

    index = {"project": graph_data["project"], "layers": {}}

    for l in graph_data["layers"]:
        lid = l["id"]
        layer_nodes = [node_map[nid] for nid in l["node_ids"] if nid in node_map]
        counter = [0]
        _chunk_recursive(l["name"], lid, layer_nodes, counter)

    # Cross-layer edges — also chunk if too large
    cross = []
    for e in edges:
        sl = node_to_layer.get(e["source"])
        tl = node_to_layer.get(e["target"])
        if sl and tl and sl != tl:
            cross.append([id_to_name.get(e["source"], ""), id_to_name.get(e["target"], ""), e["type"][0], sl, tl])

    if cross:
        cross_json = json.dumps(cross, separators=(",", ":"))
        if len(cross_json) // 4 > MAX_CHUNK_TOKENS:
            # Split cross-layer by source layer
            from collections import defaultdict
            by_src = defaultdict(list)
            for row in cross:
                by_src[row[3]].append(row)
            for i, (src_layer, rows) in enumerate(sorted(by_src.items())):
                fname = f"cross_{src_layer}.json"
                cdata = {"_": "[src,tgt,type,src_layer,tgt_layer]", "edges": rows}
                (layers_dir / fname).write_text(json.dumps(cdata, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                fsize = (layers_dir / fname).stat().st_size
                index.setdefault("cross_layer", []).append({
                    "file": f"layers/{fname}", "source_layer": src_layer,
                    "edges": len(rows), "size_kb": round(fsize / 1024), "est_tokens": round(fsize / 4),
                })
        else:
            cross_data = {"_": "[src,tgt,type,src_layer,tgt_layer]", "edges": cross}
            (layers_dir / "cross_layer.json").write_text(
                json.dumps(cross_data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            fsize = (layers_dir / "cross_layer.json").stat().st_size
            index["cross_layer"] = {
                "file": "layers/cross_layer.json", "edges": len(cross),
                "size_kb": round(fsize / 1024), "est_tokens": round(fsize / 4),
            }

    (output_dir / "graph-index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
