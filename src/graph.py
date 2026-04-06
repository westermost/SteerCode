import re, hashlib
from pathlib import Path
from dataclasses import asdict
from typing import List, Dict, Set, Tuple
from .types import GraphNode, GraphEdge, Layer
from .scanner import detect_language, CODE_LANGS
from .parser import parse_file
from .ui import progress_bar

def make_id(path: str, name: str = "") -> str:
    raw = f"{path}::{name}" if name else path
    return hashlib.md5(raw.encode()).hexdigest()[:12]

def estimate_complexity(line_count: int) -> str:
    if line_count <= 20: return "simple"
    if line_count <= 80: return "moderate"
    return "complex"

def build_graph(root: Path, files: List[Path]) -> dict:
    node_map: Dict[str, dict] = {}
    edge_set: Set[Tuple[str,str,str]] = set()
    edges: List[dict] = []
    file_id_map: Dict[str, str] = {}
    symbol_map: Dict[str, str] = {}
    import_map: Dict[str, List[dict]] = {}

    def add_node(n: dict):
        if n["id"] not in node_map: node_map[n["id"]] = n

    def add_edge(source: str, target: str, etype: str, weight: float = 0.5):
        key = (source, target, etype)
        if key not in edge_set:
            edge_set.add(key)
            edges.append(asdict(GraphEdge(source=source, target=target, type=etype, weight=weight)))

    total = len(files)
    file_contents: Dict[str, str] = {}

    for idx, fp in enumerate(files, 1):
        rel = str(fp.relative_to(root)).replace("\\", "/")
        progress_bar(idx, total, f"Parsing {fp.name[:40]}")
        lang = detect_language(fp)
        try: content = fp.read_text(errors="ignore")
        except Exception: continue

        line_count = content.count("\n") + 1
        fid = make_id(rel)
        file_id_map[rel] = fid

        add_node(asdict(GraphNode(id=fid, type="file", name=fp.name, file_path=rel,
            line_range=(1, line_count), summary=f"{lang} file ({line_count} lines)",
            tags=[lang], language=lang, complexity=estimate_complexity(line_count))))

        if lang not in CODE_LANGS: continue
        file_contents[rel] = content
        parsed = parse_file(content, lang, rel)

        for fn in parsed.functions:
            nid = make_id(rel, fn["name"])
            symbol_map[fn["name"]] = nid
            fn_lines = fn["line_end"] - fn["line_start"] + 1
            summary = f"Function with {len(fn['params'])} params" if fn["params"] else "Function"
            if fn.get("decorators"): summary += f" @{','.join(fn['decorators'])}"
            add_node(asdict(GraphNode(id=nid, type="function", name=fn["name"], file_path=rel,
                line_range=(fn["line_start"], fn["line_end"]), summary=summary,
                tags=fn.get("decorators", []), language=lang, complexity=estimate_complexity(fn_lines))))
            add_edge(fid, nid, "contains")

        for cls in parsed.classes:
            nid = make_id(rel, cls["name"])
            symbol_map[cls["name"]] = nid
            cls_lines = cls["line_end"] - cls["line_start"] + 1
            summary = f"Class with {len(cls['methods'])} methods"
            if cls.get("bases"): summary += f", extends {', '.join(cls['bases'])}"
            add_node(asdict(GraphNode(id=nid, type="class", name=cls["name"], file_path=rel,
                line_range=(cls["line_start"], cls["line_end"]), summary=summary,
                tags=cls.get("decorators", []), language=lang, complexity=estimate_complexity(cls_lines))))
            add_edge(fid, nid, "contains")
            for base in cls.get("bases", []):
                if base in symbol_map: add_edge(nid, symbol_map[base], "inherits", 0.8)

        import_map[fid] = parsed.imports

    # Resolve imports
    name_to_fid: Dict[str, str] = {}
    for rel, fid in file_id_map.items():
        stem = Path(rel).stem
        name_to_fid[stem] = fid
        no_ext = str(Path(rel).with_suffix(""))
        name_to_fid[no_ext] = fid
        name_to_fid[stem.lower()] = fid
        name_to_fid[no_ext.lower()] = fid

    for fid, imports in import_map.items():
        for imp in imports:
            source = imp["source"]
            target_fid = None
            for candidate in [source, source.replace(".","/"), source.replace("\\","/"),
                              source.split(".")[-1], source.split("/")[-1], source.split("\\")[-1]]:
                c = candidate.lower() if candidate else ""
                if c in name_to_fid: target_fid = name_to_fid[c]; break
            if target_fid and target_fid != fid: add_edge(fid, target_fid, "imports", 0.6)

    # Cross-reference
    SKIP_NAMES = {"get","set","run","init","main","test","setup","call","new","open","close",
                  "read","write","next","send","load","save","start","stop","add","remove",
                  "update","delete","create","find","show","hide","log","print","push","pop",
                  "put","map","then","catch","from","to","on","off","emit","use","has"}
    func_names = {n["name"]: n["id"] for n in node_map.values()
                  if n["type"] == "function" and len(n["name"]) >= 3 and n["name"] not in SKIP_NAMES}
    _call_re = re.compile(r"\b(\w+)\s*\(")
    func_name_set = set(func_names.keys())

    code_rels = list(file_contents.keys())
    for idx, rel in enumerate(code_rels, 1):
        progress_bar(idx, len(code_rels), f"Cross-ref {Path(rel).name[:40]}")
        fid = file_id_map[rel]
        called = set(_call_re.findall(file_contents[rel])) & func_name_set
        for fname in called:
            if (fid, func_names[fname], "contains") not in edge_set:
                add_edge(fid, func_names[fname], "calls", 0.4)

    del file_contents
    return {"nodes": list(node_map.values()), "edges": edges, "file_id_map": file_id_map}

# ─── Layer Detection ──────────────────────────────────────────────────────────

LAYER_RULES = [
    ("api",     "API / Routes",     ["route","controller","handler","endpoint","api","router","view","views"]),
    ("ui",      "UI / Frontend",    ["component","page","layout","template","widget","screen","ui","frontend","src/app"]),
    ("service", "Service / Logic",  ["service","usecase","use_case","interactor","manager","logic","domain","core"]),
    ("data",    "Data / Storage",   ["model","schema","entity","repository","repo","dao","migration","database","db","store"]),
    ("infra",   "Infrastructure",   ["config","middleware","plugin","util","helper","lib","common","shared","infra","infrastructure"]),
    ("test",    "Tests",            ["test","spec","tests","specs","__tests__","e2e","integration"]),
    ("docs",    "Documentation",    ["doc","docs","readme","guide","tutorial"]),
]

def detect_layers(nodes: List[dict]) -> List[dict]:
    layers: Dict[str, Layer] = {lid: Layer(id=lid, name=name, description=name) for lid, name, _ in LAYER_RULES}
    for node in nodes:
        fp = node.get("file_path", "").lower()
        name = node.get("name", "").lower()
        assigned = False
        for lid, _, keywords in LAYER_RULES:
            if any(kw in fp.split("/") or kw in name for kw in keywords):
                layers[lid].node_ids.append(node["id"]); assigned = True; break
        if not assigned:
            lang = node.get("language", "")
            if lang in ("markdown","html"): layers["docs"].node_ids.append(node["id"])
            elif lang in ("json","yaml","toml","dockerfile","terraform"): layers["infra"].node_ids.append(node["id"])
            else: layers["service"].node_ids.append(node["id"])
    return [asdict(l) for l in layers.values() if l.node_ids]
