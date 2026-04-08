"""Steering file generation for AI tools."""

from pathlib import Path
from collections import defaultdict
from typing import List


STEERING_TARGETS = [
    ("kiro",    ".kiro/steering",  "knowledge-graph.md",      True),
    ("cursor",  ".cursor/rules",   "knowledge-graph.md",      True),
    ("copilot", ".github",         "copilot-instructions.md", True),
    ("claude",  ".",               "CLAUDE.md",               False),
    ("windsurf",".",               ".windsurfrules",          False),
    ("cline",   ".",               ".clinerules",             False),
    ("codex",   ".",               "AGENTS.md",               False),
]

TOOL_NAMES = [t[0] for t in STEERING_TARGETS]


def _build_steering_content(graph_data: dict) -> str:
    p = graph_data["project"]
    layers_summary = "\n".join(f"- **{l['name']}**: {len(l['node_ids'])} nodes" for l in graph_data["layers"])
    node_counts = defaultdict(int)
    for n in graph_data["nodes"]: node_counts[n["type"]] += 1
    stats = ", ".join(f"{c} {t}{'es' if t == 'class' else 's'}" for t, c in sorted(node_counts.items(), key=lambda x: -x[1]))

    # Version info
    versions = p.get("versions") or {}
    version_lines = ""
    if any(versions.values()):
        parts = []
        for name, ver in versions.get("runtime", {}).items():
            parts.append(f"  - {name}: {ver}")
        for name, ver in versions.get("frameworks", {}).items():
            parts.append(f"  - {name}: {ver}")
        for mgr, info in versions.get("packages", {}).items():
            parts.append(f"  - {mgr}: {info['count']} packages")
            for pkg, ver in info.get("key", {}).items():
                parts.append(f"    - {pkg}: {ver}")
        if parts:
            version_lines = "\n## Versions & Dependencies\n" + "\n".join(parts)

    # Key Nodes = hub nodes (most connections) — these are the real core of the codebase
    edge_count = {}
    for e in graph_data["edges"]:
        edge_count[e["source"]] = edge_count.get(e["source"], 0) + 1
        edge_count[e["target"]] = edge_count.get(e["target"], 0) + 1

    _SKIP_PATHS = {"vendor", "node_modules", "library", "jquery", "npm", "bower_components", "@types",
                   "smarty", "mojavi", "jpgraph", "prototype", "tiny_mce", "ckeditor",
                   "bootstrap", "fontawesome", "swiper", "lodash", "underscore"}
    _SKIP_NAMES = {"__construct", "toString", "valueOf", "hasOwnProperty", "preventDefault",
                   "stopPropagation", "addEventListener", "removeEventListener", "querySelector",
                   "getElementById", "jQuery", "require", "define", "exports", "module",
                   "is_array", "is_null", "is_string", "isset", "empty", "count", "array_merge",
                   "array_map", "array_filter", "array_keys", "array_values", "explode", "implode",
                   "sprintf", "preg_match", "str_replace", "substr", "strlen", "trim",
                   "setTimeout", "setInterval", "console", "bind", "call", "apply",
                   "list", "all", "get", "set", "run", "text", "prop", "attr", "each",
                   "replace", "compact", "push", "pop", "map", "filter", "find", "sort",
                   "add", "remove", "show", "hide", "open", "close", "next", "log",
                   "join", "merge", "split", "slice", "index", "fetch", "store",
                   "encode", "decode", "parse", "format", "validate", "check",
                   "initialize", "init", "setup", "configure", "reset", "destroy",
                   "post", "put", "patch", "delete", "head", "options",
                   "to_s", "to_i", "to_a", "to_h", "inspect", "respond_to",
                   "subject", "body", "header", "params", "request", "response",
                   "match", "warn", "select", "convert", "sanitize", "error",
                   "send", "write", "read", "create", "update", "save", "load",
                   "start", "stop", "test", "new", "type", "name", "value", "data",
                   "result", "info", "debug", "render", "build", "generate"}

    def _is_project_node(n):
        fp = n.get("file_path", "").lower()
        return (n.get("name") and n["name"] not in _SKIP_NAMES
                and not any(s in fp.split("/") for s in _SKIP_PATHS))

    top_nodes = sorted(
        [n for n in graph_data["nodes"] if n["type"] in ("class", "function") and _is_project_node(n)],
        key=lambda n: (
            -edge_count.get(n["id"], 0),
            0 if n.get("complexity") == "complex" else (1 if n.get("complexity") == "moderate" else 2),
            0 if n["type"] == "class" else 1,
            -len(str(n.get("summary", ""))),  # prefer nodes with LLM summaries
        ))[:30]
    top_ref = "\n".join(
        f"- `{n['name']}` ({n['type']}, {n.get('complexity','')}) in `{n.get('file_path','')}`"
        + (f" — domain: {n['semantics']['domain_hint']}" if n.get('semantics', {}).get('domain_hint') else "")
        + (f", role: {n['semantics']['execution_role']}" if n.get('semantics', {}).get('execution_role') else "")
        + (f", effects: {', '.join(e['type'] for e in n['semantics'].get('side_effects', []))}" if n.get('semantics', {}).get('side_effects') else "")
        for n in top_nodes)

    return f"""# Codebase Knowledge Graph

Auto-generated by SteerCode. Re-run `python steercode.py .` to update.

## Project: {p['name']}
- Languages: {', '.join(p.get('languages', []))}
- {stats}
- Knowledge graph: `.codemap-output/knowledge-graph.compact.json`

## Architectural Layers
{layers_summary}
{version_lines}
## Key Nodes
{top_ref}

## Instructions for AI

### Before modifying code
1. Read `.codemap-output/graph-index.json` — it lists all layers with file paths and sizes
2. Load ONLY the layer(s) relevant to your task from `.codemap-output/layers/<layer>.json`
3. If you need cross-layer dependencies, load `.codemap-output/layers/cross_layer.json`
4. For full graph (if needed): `.codemap-output/knowledge-graph.compact.json`

### Progressive Loading (recommended for large codebases)
```
graph-index.json          ← Read first (tiny, lists all layers + sizes)
layers/
  <layer>.json            ← Load layer(s) relevant to your task
  cross_layer.json        ← Load to trace cross-layer dependencies
knowledge-graph.compact.json  ← Full graph in columnar format (fallback)
```

### Layer File Schema (columnar — headers once, data as arrays)
- `paths[]`: indexed file paths (referenced by index in nodes)
- `nodes[]`: `[path_idx, type, name, summary, complexity]` — type: F=file, f=function, C=class — complexity: !=complex, ~=moderate
- `edges[]`: `[source_name, target_name, type_char]` — type: i=imports, c=contains, >=calls, ^=inherits

### Impact analysis
To find what changing function X affects: find node X → follow outgoing "calls"/"imports" edges → list affected nodes.
"""


def generate_steering(graph_data: dict, root: Path, output_dir: Path, tools: List[str] = None) -> List[str]:
    """Generate steering files for selected AI tools (all if tools is None)."""
    content = _build_steering_content(graph_data)
    paths = []
    selected = [t for t in STEERING_TARGETS if tools is None or t[0] in tools]

    for name, dir_rel, filename, auto in selected:
        if auto:
            target_dir = root / dir_rel
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / filename).write_text(content, encoding="utf-8")
            paths.append(str((target_dir / filename).relative_to(root)))
        else:
            steering_dir = output_dir / "steering"
            steering_dir.mkdir(parents=True, exist_ok=True)
            (steering_dir / filename).write_text(content, encoding="utf-8")
            paths.append(str((steering_dir / filename).relative_to(root) if steering_dir.is_relative_to(root) else steering_dir / filename))

    return paths
