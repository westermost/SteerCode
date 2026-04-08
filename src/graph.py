import re, hashlib
from pathlib import Path
from collections import defaultdict
from dataclasses import asdict
from typing import List, Dict, Set, Tuple
from .types import GraphNode, GraphEdge, Layer, SemanticInfo
from .scanner import detect_language, CODE_LANGS
from .parsers import parse_file
from .parsers.semantics import extract_semantics, _detect_role, _detect_domain
from .ui import progress_bar
from .complexity import estimate_complexity

def make_id(path: str, name: str = "") -> str:
    raw = f"{path}::{name}" if name else path
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def build_graph(root: Path, files: List[Path]) -> dict:
    ctx = _GraphContext()
    _parse_files(ctx, root, files)
    _resolve_imports(ctx)
    _cross_reference_calls(ctx)
    del ctx.file_contents
    return {"nodes": list(ctx.node_map.values()), "edges": ctx.edges, "file_id_map": ctx.file_id_map}


class _GraphContext:
    def __init__(self):
        self.node_map: Dict[str, dict] = {}
        self.edge_set: Set[Tuple[str,str,str]] = set()
        self.edges: List[dict] = []
        self.file_id_map: Dict[str, str] = {}
        self.symbol_map: Dict[str, str] = {}
        self.import_map: Dict[str, List[dict]] = {}
        self.file_contents: Dict[str, str] = {}

    def add_node(self, n: dict):
        if n["id"] not in self.node_map: self.node_map[n["id"]] = n

    def add_edge(self, source: str, target: str, etype: str, weight: float = 0.5):
        key = (source, target, etype)
        if key not in self.edge_set:
            self.edge_set.add(key)
            self.edges.append(asdict(GraphEdge(source=source, target=target, type=etype, weight=weight)))


def _parse_files(ctx: '_GraphContext', root: Path, files: List[Path]):
    total = len(files)
    for idx, fp in enumerate(files, 1):
        rel = str(fp.relative_to(root)).replace("\\", "/")
        progress_bar(idx, total, f"Parsing {fp.name[:40]}")
        lang = detect_language(fp)
        try: content = fp.read_text(errors="ignore")
        except Exception: continue

        line_count = content.count("\n") + 1
        fid = make_id(rel)
        ctx.file_id_map[rel] = fid

        ctx.add_node(asdict(GraphNode(id=fid, type="file", name=fp.name, file_path=rel,
            line_range=(1, line_count), summary=f"{lang} file ({line_count} lines)",
            tags=[lang], language=lang, complexity=estimate_complexity(line_count, content, lang))))

        if lang not in CODE_LANGS: continue
        ctx.file_contents[rel] = content
        parsed = parse_file(content, lang, rel)
        import_sources = [imp.get("source", "") for imp in parsed.imports]

        # Pre-compute file-level semantics once (fast), then per-function only name/role
        file_sem = extract_semantics(content, fp.name, rel, import_sources, lang)

        for fn in parsed.functions:
            nid = make_id(rel, fn["name"])
            ctx.symbol_map[fn["name"]] = nid
            fn_lines = fn["line_end"] - fn["line_start"] + 1
            fn_source = "\n".join(content.splitlines()[fn["line_start"]-1:fn["line_end"]])
            summary = f"Function with {len(fn['params'])} params" if fn["params"] else "Function"
            if fn.get("decorators"): summary += f" @{','.join(fn['decorators'])}"
            # Lightweight per-function: inherit file effects, detect role from name
            sem = SemanticInfo(
                side_effects=file_sem.side_effects[:],
                control_flow=file_sem.control_flow[:],
                domain_hint=_detect_domain(fn["name"], fn_source, rel),
                execution_role=_detect_role(fn["name"], rel),
            )
            node = asdict(GraphNode(id=nid, type="function", name=fn["name"], file_path=rel,
                line_range=(fn["line_start"], fn["line_end"]), summary=summary,
                tags=fn.get("decorators", []), language=lang, complexity=estimate_complexity(fn_lines, fn_source, lang)))
            node["semantics"] = asdict(sem)
            ctx.add_node(node)
            ctx.add_edge(fid, nid, "contains")

        for cls in parsed.classes:
            nid = make_id(rel, cls["name"])
            ctx.symbol_map[cls["name"]] = nid
            cls_lines = cls["line_end"] - cls["line_start"] + 1
            cls_source = "\n".join(content.splitlines()[cls["line_start"]-1:cls["line_end"]])
            summary = f"Class with {len(cls['methods'])} methods"
            if cls.get("bases"): summary += f", extends {', '.join(cls['bases'])}"
            sem = SemanticInfo(
                side_effects=file_sem.side_effects[:],
                control_flow=file_sem.control_flow[:],
                domain_hint=_detect_domain(cls["name"], cls_source, rel),
                execution_role=_detect_role(cls["name"], rel),
            )
            node = asdict(GraphNode(id=nid, type="class", name=cls["name"], file_path=rel,
                line_range=(cls["line_start"], cls["line_end"]), summary=summary,
                tags=cls.get("decorators", []), language=lang, complexity=estimate_complexity(cls_lines, cls_source, lang)))
            node["semantics"] = asdict(sem)
            ctx.add_node(node)
            ctx.add_edge(fid, nid, "contains")
            for base in cls.get("bases", []):
                if base in ctx.symbol_map: ctx.add_edge(nid, ctx.symbol_map[base], "inherits", 0.8)

        ctx.import_map[fid] = parsed.imports


def _resolve_imports(ctx: '_GraphContext'):
    name_to_fid: Dict[str, str] = {}
    for rel, fid in ctx.file_id_map.items():
        stem = Path(rel).stem
        name_to_fid[stem] = fid
        no_ext = str(Path(rel).with_suffix(""))
        name_to_fid[no_ext] = fid
        name_to_fid[stem.lower()] = fid
        name_to_fid[no_ext.lower()] = fid

    for fid, imports in ctx.import_map.items():
        for imp in imports:
            source = imp["source"]
            target_fid = None
            for candidate in [source, source.replace(".","/"), source.replace("\\","/"),
                              source.split(".")[-1], source.split("/")[-1], source.split("\\")[-1]]:
                c = candidate.lower() if candidate else ""
                if c in name_to_fid: target_fid = name_to_fid[c]; break
            if target_fid and target_fid != fid: ctx.add_edge(fid, target_fid, "imports", 0.6)


def _cross_reference_calls(ctx: '_GraphContext'):
    SKIP_NAMES = {"get","set","run","init","main","test","setup","call","new","open","close",
                  "read","write","next","send","load","save","start","stop","add","remove",
                  "update","delete","create","find","show","hide","log","print","push","pop",
                  "put","map","then","catch","from","to","on","off","emit","use","has"}
    func_names = {n["name"]: n["id"] for n in ctx.node_map.values()
                  if n["type"] == "function" and len(n["name"]) >= 3 and n["name"] not in SKIP_NAMES}
    _call_re = re.compile(r"\b(\w+)\s*\(")
    func_name_set = set(func_names.keys())

    code_rels = list(ctx.file_contents.keys())
    for idx, rel in enumerate(code_rels, 1):
        progress_bar(idx, len(code_rels), f"Cross-ref {Path(rel).name[:40]}")
        fid = ctx.file_id_map[rel]
        called = set(_call_re.findall(ctx.file_contents[rel])) & func_name_set
        for fname in called:
            if (fid, func_names[fname], "contains") not in ctx.edge_set:
                ctx.add_edge(fid, func_names[fname], "calls", 0.4)

# ─── Layer Detection ──────────────────────────────────────────────────────────

LAYER_RULES = [
    ("api",     "API / Routes",     ["route","controller","handler","endpoint","api","router","view","views"]),
    ("ui",      "UI / Frontend",    ["component","page","layout","template","widget","screen","ui","frontend","src/app"]),
    ("service", "Service / Logic",  ["service","usecase","use_case","interactor","manager","logic","domain","core"]),
    ("data",    "Data / Storage",   ["model","schema","entity","repository","repo","dao","migration","database","db","store"]),
    ("infra",   "Infrastructure",   ["config","middleware","plugin","util","helper","lib","common","shared","infra","infrastructure"]),
    ("test",    "Tests",            ["test","spec","tests","specs","__tests__","e2e","integration"]),
    ("docs",    "Documentation",    ["docs","readme","guide","tutorial","documentation"]),
]

def detect_layers(nodes: List[dict]) -> List[dict]:
    layers: Dict[str, Layer] = {lid: Layer(id=lid, name=name, description=name) for lid, name, _ in LAYER_RULES}
    for node in nodes:
        fp = node.get("file_path", "").lower()
        name = node.get("name", "").lower()
        parts = set(fp.split("/"))
        assigned = False
        for lid, _, keywords in LAYER_RULES:
            if any(kw in parts for kw in keywords):
                layers[lid].node_ids.append(node["id"]); assigned = True; break
        if not assigned:
            lang = node.get("language", "")
            if lang == "markdown": layers["docs"].node_ids.append(node["id"])
            elif lang in ("json","yaml","toml","dockerfile","terraform","xml"): layers["infra"].node_ids.append(node["id"])
            elif lang in ("html","css"): layers["ui"].node_ids.append(node["id"])
            else: layers["service"].node_ids.append(node["id"])
    return [asdict(l) for l in layers.values() if l.node_ids]

# ─── Graph Relationships ─────────────────────────────────────────────────────

def get_callers(node_id: str, edges: List[dict]) -> List[str]:
    """Get IDs of nodes that call this node."""
    return [e["source"] for e in edges if e["target"] == node_id and e["type"] == "calls"]

def get_callees(node_id: str, edges: List[dict]) -> List[str]:
    """Get IDs of nodes that this node calls."""
    return [e["target"] for e in edges if e["source"] == node_id and e["type"] == "calls"]

# ─── Importance Scoring ──────────────────────────────────────────────────────

def compute_importance(nodes: List[dict], edges: List[dict]) -> Dict[str, float]:
    """Compute importance scores with decay by depth, normalized to percentile."""
    direct_callers = defaultdict(set)
    for e in edges:
        if e["type"] == "calls": direct_callers[e["target"]].add(e["source"])

    # Indirect callers (depth 2)
    indirect_callers = defaultdict(set)
    for target, callers in direct_callers.items():
        for caller in callers:
            for e in edges:
                if e["type"] == "calls" and e["target"] == caller:
                    indirect_callers[target].add(e["source"])

    scores = {}
    for n in nodes:
        if n["type"] not in ("function", "class"): continue
        nid = n["id"]
        sem = n.get("semantics", {})
        score = 0.0

        effects = sem.get("side_effects", [])
        if any("db_write" in str(e) for e in effects): score += 0.3
        if any("external_api" in str(e) for e in effects): score += 0.3

        score += min(len(direct_callers.get(nid, set())) * 0.1, 0.3)
        score += min(len(indirect_callers.get(nid, set())) * 0.05, 0.15)

        role = sem.get("execution_role", "")
        if role in ("entry_point", "orchestrator"): score += 0.2
        if n.get("complexity") == "complex": score += 0.1

        scores[nid] = min(score, 1.0)

    # Percentile normalization
    if scores:
        sorted_vals = sorted(set(scores.values()))
        rank_map = {v: i / max(len(sorted_vals) - 1, 1) for i, v in enumerate(sorted_vals)}
        scores = {k: round(rank_map[v], 3) for k, v in scores.items()}
    return scores


# ─── Incremental ─────────────────────────────────────────────────────────────

MAX_IMPACT_DEPTH = 2
FOLLOW_EDGE_TYPES = {"calls", "imports"}

def get_impacted_files(changed_files: Set[str], edges: List[dict], max_depth: int = MAX_IMPACT_DEPTH) -> Set[str]:
    """Bounded BFS: expand changed files to transitively affected files."""
    visited = set(changed_files)
    frontier = set(changed_files)
    for _ in range(max_depth):
        next_frontier = set()
        for f in frontier:
            for e in edges:
                if e["type"] not in FOLLOW_EDGE_TYPES: continue
                neighbor = e["target"] if e["source"] == f else (e["source"] if e["target"] == f else None)
                if neighbor and neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
        frontier = next_frontier
        if not frontier: break
    return visited


def merge_graphs(old: dict, new: dict, changed_file_paths: Set[str]) -> dict:
    """Merge new graph results into old graph, replacing nodes from changed files."""
    old_nodes = {n["id"]: n for n in old.get("nodes", [])}
    new_nodes = {n["id"]: n for n in new.get("nodes", [])}

    # Remove old nodes from changed files
    for nid, n in list(old_nodes.items()):
        if n.get("file_path") in changed_file_paths:
            del old_nodes[nid]

    # Add new nodes
    old_nodes.update(new_nodes)

    # Merge edges: remove edges involving changed files, add new ones
    old_edges = [e for e in old.get("edges", [])
                 if not any(old.get("nodes", [{}])[0].get("file_path") in changed_file_paths
                           for _ in [0])]  # keep all old edges for simplicity
    new_edge_set = {(e["source"], e["target"], e["type"]) for e in new.get("edges", [])}
    merged_edges = [e for e in old.get("edges", [])
                    if (e["source"], e["target"], e["type"]) not in new_edge_set]
    merged_edges.extend(new.get("edges", []))

    return {"nodes": list(old_nodes.values()), "edges": merged_edges,
            "file_id_map": {**old.get("file_id_map", {}), **new.get("file_id_map", {})}}
