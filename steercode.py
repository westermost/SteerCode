#!/usr/bin/env python3
"""SteerCode — Scan your codebase. Steer your AI."""

import json, os, sys, webbrowser
from pathlib import Path

# Force unbuffered stdout for real-time progress bars on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(write_through=True)
elif not getattr(sys.stdout, 'isatty', lambda: False)():
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
from collections import defaultdict
from datetime import datetime, timezone

from src import (
    scan_files, detect_language, build_graph, detect_layers,
    enrich_with_llm, generate_dashboard, generate_steering,
    detect_versions, compute_importance,
    C, banner, phase_header, phase_done, table, summary_box, prompt,
    TOOL_NAMES,
)
from src.scanner import compute_fingerprints, diff_fingerprints, load_fingerprints, save_fingerprints

# ─── Config Persistence ──────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".steercode.json"

def load_config() -> dict:
    try: return json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    except Exception: return {}

def save_config(cfg: dict):
    try: CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    except Exception: pass

# ─── Interactive Wizard ───────────────────────────────────────────────────────

def interactive_setup() -> dict:
    saved = load_config()
    banner()
    print(f"  {C.WHITE}{C.BOLD}Welcome! Let's analyze your codebase.{C.RST}")
    print(f"  {C.DIM}Press Enter to accept defaults shown in [brackets].{C.RST}")
    if saved:
        print(f"  {C.DIM}Settings loaded from {CONFIG_PATH}{C.RST}")
    print()

    # Project path
    cwd = os.getcwd()
    path = prompt("Project path", saved.get("last_path", cwd))
    p = Path(path).resolve()
    while not p.is_dir():
        print(f"    {C.RED}✗ Not a valid directory{C.RST}")
        path = prompt("Project path", cwd)
        p = Path(path).resolve()
    print()

    # LLM enrichment
    print(f"  {C.WHITE}LLM Enrichment{C.RST} {C.DIM}(optional — requires LM Studio / Ollama running locally){C.RST}")
    use_llm = prompt("Enable LLM?", saved.get("use_llm", "no"), ["yes", "no"])
    llm_url, model, context_size = "", "", 8192
    if use_llm == "yes":
        llm_url = prompt("LLM URL", saved.get("llm_url", "http://localhost:1234"))
        model = prompt("Model name (leave empty for default)", saved.get("model", ""))
        ctx = prompt("Context size in tokens", str(saved.get("context_size", 8192)))
        context_size = int(ctx) if ctx.isdigit() else 8192
    print()

    # Output
    output = prompt("Output directory", saved.get("output", ".codemap-output"))
    no_open = prompt("Open dashboard in browser?", saved.get("open_browser", "yes"), ["yes", "no"]) == "no"
    print()

    # Tool selection
    print(f"  {C.WHITE}Steering Targets{C.RST} {C.DIM}(which AI tools to generate steering for){C.RST}")
    print(f"    {C.DIM}Available: {', '.join(TOOL_NAMES)}{C.RST}")
    tools_input = prompt("Tools (comma-separated, or 'all')", saved.get("tools", "all"))
    if tools_input.strip().lower() == "all":
        selected_tools = None
    else:
        selected_tools = [t.strip().lower() for t in tools_input.split(",") if t.strip().lower() in TOOL_NAMES]
        if not selected_tools:
            print(f"    {C.YELLOW}⚠ No valid tools, using all{C.RST}")
            selected_tools = None
    print()

    save_config({"last_path": str(p), "use_llm": use_llm, "llm_url": llm_url,
        "model": model, "context_size": context_size, "output": output,
        "open_browser": "no" if no_open else "yes",
        "tools": tools_input})
    print(f"  {C.DIM}Settings saved to {CONFIG_PATH}{C.RST}\n")

    return {"path": [str(p)], "output": output, "no_open": no_open, "json_only": False,
            "llm": llm_url, "model": model, "context_size": context_size,
            "tools": selected_tools}

# ─── Main ─────────────────────────────────────────────────────────────────────

def _parse_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="SteerCode — Scan your codebase. Steer your AI.",
        epilog="Example: python steercode.py ./my-project -o .codemap-output")
    parser.add_argument("path", nargs="*", default=["."], help="Path to codebase")
    parser.add_argument("-o", "--output", default=".codemap-output", help="Output directory")
    parser.add_argument("--no-open", action="store_true", help="Don't open dashboard in browser")
    parser.add_argument("--json-only", action="store_true", help="Only output JSON, skip dashboard")
    parser.add_argument("--full", action="store_true", help="Force full rebuild (ignore fingerprints)")
    parser.add_argument("--llm", default="", help="Local LLM URL (e.g. http://localhost:1234)")
    parser.add_argument("--model", default="", help="Model name (optional)")
    parser.add_argument("--context-size", type=int, default=8192, help="LLM context size in tokens")
    parser.add_argument("--max-enrich", type=int, default=0, help="Max nodes to enrich with LLM")
    parser.add_argument("--tools", default=None, help=f"Comma-separated AI tools to generate steering for ({','.join(TOOL_NAMES)})")
    args = parser.parse_args()
    if args.tools:
        args.tools = [t.strip().lower() for t in args.tools.split(",") if t.strip().lower() in TOOL_NAMES]
        if not args.tools: args.tools = None
    return args


def _run_pipeline(args, root, output_dir, llm_url, use_llm):
    import time
    from src.config import load_config
    load_config(root)
    t0 = time.time()

    # Auto-add output dir to .gitignore if git repo exists
    gitignore = root / ".gitignore"
    if (root / ".git").is_dir():
        output_rel = str(output_dir.relative_to(root)) + "/" if output_dir.is_relative_to(root) else None
        if output_rel:
            existing = gitignore.read_text(errors="ignore") if gitignore.exists() else ""
            if output_rel.rstrip("/") not in existing and output_rel not in existing:
                with open(gitignore, "a") as f:
                    if existing and not existing.endswith("\n"): f.write("\n")
                    f.write(f"\n# SteerCode output\n{output_rel}\n")

    total_phases = 5 if use_llm else 4
    phase = 0

    # Phase 1: Scan
    phase += 1
    phase_header(phase, total_phases, "Scanning files")
    def _scan_progress(count, name):
        throttle = 50
        try:
            from src import config as cfg_mod
            throttle = cfg_mod.get("scan", "progress_throttle")
        except Exception: pass
        if count % throttle == 0 or count < 5:
            sys.stdout.write(f"\r\033[K    {C.DIM}{count} files found — {name[:50]}{C.RST}")
            sys.stdout.flush()
    files = scan_files(root, on_progress=_scan_progress)
    sys.stdout.write("\r\033[K")  # clear progress line
    if not files:
        print(f"  {C.YELLOW}  ⚠ No supported files found.{C.RST}"); sys.exit(0)
    lang_counts = defaultdict(int)
    for f in files: lang_counts[detect_language(f)] += 1
    t1 = time.time()
    phase_done(f"{len(files):,} files across {len(lang_counts)} languages", t1 - t0)
    table([(l, f"{c:,}") for l, c in sorted(lang_counts.items(), key=lambda x: -x[1])[:8]])

    # Fingerprints for incremental
    fp_path = output_dir / "fingerprints.json"
    sys.stdout.write(f"    {C.DIM}Computing fingerprints...{C.RST}")
    sys.stdout.flush()
    new_fps = compute_fingerprints(root, files)
    sys.stdout.write(f"\r\033[K")
    old_fps = load_fingerprints(fp_path) if not getattr(args, "full", False) else None
    if old_fps:
        diff = diff_fingerprints(old_fps, new_fps)
        changed = len(diff["added"]) + len(diff["modified"]) + len(diff["removed"])
        if changed == 0 and not use_llm:
            phase_done("No files changed since last run", 0)
            save_fingerprints(new_fps, fp_path)
            return
        sys.stdout.write(f"    {C.DIM}Incremental: {len(diff['added'])} added, {len(diff['modified'])} modified, {len(diff['removed'])} removed{C.RST}\n")
    save_fingerprints(new_fps, fp_path)
    print()

    # Phase 2: Parse
    phase += 1
    phase_header(phase, total_phases, "Parsing & building knowledge graph")
    result = build_graph(root, files)
    t2 = time.time()
    node_types = defaultdict(int)
    for n in result["nodes"]: node_types[n["type"]] += 1
    phase_done(f"{len(result['nodes']):,} nodes, {len(result['edges']):,} edges", t2 - t1)
    table([(t, f"{c:,}") for t, c in sorted(node_types.items(), key=lambda x: -x[1])])
    print()

    # Phase 3: LLM (optional)
    if use_llm:
        phase += 1
        phase_header(phase, total_phases, f"Enriching summaries with {C.MAGENTA}local LLM{C.RST} {C.DIM}({llm_url}){C.RST}")
        enriched = enrich_with_llm(result["nodes"], result["edges"], root,
            llm_url, args.model, getattr(args, "context_size", 8192), getattr(args, "max_enrich", 0),
            output_dir=output_dir)
        t_llm = time.time()
        phase_done(f"{enriched:,} nodes enriched", t_llm - t2)
        print(); t2 = t_llm

    # Phase 4: Layers
    phase += 1
    phase_header(phase, total_phases, "Detecting architectural layers")
    layer_data = detect_layers(result["nodes"])
    t3 = time.time()
    phase_done(f"{len(layer_data)} layers detected", t3 - t2)
    table([(l["name"], f"{len(l['node_ids']):,} nodes") for l in layer_data])
    print()

    # Assemble graph
    # Detect versions
    llm_ver_fn = None
    if use_llm:
        from src.llm import _llm_request
        llm_ver_fn = lambda prompt: _llm_request(llm_url, args.model, prompt)
    versions = detect_versions(root, llm_fn=llm_ver_fn)

    graph_data = {
        "version": "1.0.0",
        "project": {"name": root.name, "languages": list(lang_counts.keys()),
            "description": f"Knowledge graph for {root.name}",
            "analyzedAt": datetime.now(timezone.utc).isoformat(), "llmEnriched": use_llm,
            "versions": versions},
        "nodes": result["nodes"], "edges": result["edges"], "layers": layer_data,
    }

    if getattr(args, "json_only", False):
        output_dir.mkdir(parents=True, exist_ok=True)
        kg_path = output_dir / "knowledge-graph.json"
        kg_path.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False), encoding="utf-8")
        summary_box([f"📊 Knowledge graph saved to {kg_path}"])
        return

    # Phase 5: Dashboard
    phase += 1
    phase_header(phase, total_phases, "Generating dashboard")
    dash_path, kg_path = generate_dashboard(graph_data, output_dir)
    steering_paths = generate_steering(graph_data, root, output_dir, getattr(args, "tools", None))
    t4 = time.time()
    phase_done(f"Dashboard + {len(steering_paths)} steering files ready", t4 - t3)

    steering_list = ", ".join(steering_paths[:3]) + (f" +{len(steering_paths)-3} more" if len(steering_paths) > 3 else "")
    summary_box([
        f"{C.GREEN}{C.BOLD}✅ Done in {t4-t0:.1f}s{C.RST}", "",
        f"📊 Graph:     {C.WHITE}{kg_path}{C.RST}",
        f"🌐 Dashboard: {C.WHITE}{dash_path}{C.RST}",
        f"🤖 Steering:  {C.WHITE}{steering_list}{C.RST}", "",
        f"{C.DIM}Nodes: {len(result['nodes']):,}  │  Edges: {len(result['edges']):,}  │  Layers: {len(layer_data)}{C.RST}",
    ])

    if not getattr(args, "no_open", False):
        print(f"  {C.BLUE}Opening dashboard in browser...{C.RST}\n")
        webbrowser.open(f"file://{dash_path}")


# ─── Query Command ────────────────────────────────────────────────────────────

def _run_query(args):
    """Handle: steercode query <command> [args]"""
    from src.query import GraphQuery
    import json as _json

    graph_path = Path(".codemap-output/knowledge-graph.json")
    if not graph_path.exists():
        print(f"{C.RED}  ✗ No knowledge graph found. Run 'python steercode.py .' first.{C.RST}")
        sys.exit(1)

    q = GraphQuery(str(graph_path))

    if not args:
        print(f"  {C.WHITE}Usage:{C.RST}")
        print(f"    steercode query find [--type T] [--domain D] [--effect E] [--name N]")
        print(f"    steercode query impact <function_name>")
        print(f"    steercode query flow <from> <to>")
        print(f"    steercode query explain <function_name>")
        return

    cmd = args[0]

    if cmd == "find":
        kwargs = {}
        i = 1
        while i < len(args):
            if args[i] == "--type" and i + 1 < len(args): kwargs["node_type"] = args[i+1]; i += 2
            elif args[i] == "--domain" and i + 1 < len(args): kwargs["domain"] = args[i+1]; i += 2
            elif args[i] == "--effect" and i + 1 < len(args): kwargs["effect"] = args[i+1]; i += 2
            elif args[i] == "--name" and i + 1 < len(args): kwargs["name"] = args[i+1]; i += 2
            else: i += 1
        results = q.find(**kwargs)
        for n in results:
            eff = f" effects={n.get('effects')}" if n.get("effects") else ""
            dom = f" domain={n.get('domain')}" if n.get("domain") else ""
            print(f"  {C.BGREEN}{n['name']}{C.RST} ({n['type']}) in {n.get('file_path','')}{dom}{eff}")
        print(f"\n  {C.DIM}{len(results)} results{C.RST}")

    elif cmd == "impact" and len(args) > 1:
        results = q.impact(args[1])
        for n in results:
            print(f"  {C.BGREEN}{n['name']}{C.RST} ({n['type']}) in {n.get('file_path','')}")
        print(f"\n  {C.DIM}{len(results)} impacted nodes{C.RST}")

    elif cmd == "flow" and len(args) > 2:
        path = q.flow(args[1], args[2])
        if path:
            print(f"  {' → '.join(C.BGREEN + n['name'] + C.RST for n in path)}")
        else:
            print(f"  {C.YELLOW}No path found{C.RST}")

    elif cmd == "explain" and len(args) > 1:
        info = q.explain(args[1])
        if info:
            print(_json.dumps(info, indent=2))
        else:
            print(f"  {C.YELLOW}Node not found: {args[1]}{C.RST}")

    else:
        print(f"  {C.YELLOW}Unknown query command: {cmd}{C.RST}")


def _run_tour(args):
    """Handle: steercode tour [--focus domain]"""
    import json as _json
    from src.tour import generate_tour, format_tour
    graph_path = Path(".codemap-output/knowledge-graph.json")
    if not graph_path.exists():
        print(f"{C.RED}  ✗ No knowledge graph. Run 'python steercode.py .' first.{C.RST}"); sys.exit(1)
    focus = None
    if args and args[0] == "--focus" and len(args) > 1: focus = args[1]
    graph_data = _json.loads(graph_path.read_text())
    stops = generate_tour(graph_data, focus)
    print(format_tour(stops, graph_data["project"]["name"]))


def _run_domain(args):
    """Handle: steercode domain [--llm URL]"""
    import json as _json
    from src.domain import extract_domains, format_domains
    graph_path = Path(".codemap-output/knowledge-graph.json")
    if not graph_path.exists():
        print(f"{C.RED}  ✗ No knowledge graph. Run 'python steercode.py .' first.{C.RST}"); sys.exit(1)
    llm_url, model = "", ""
    i = 0
    while i < len(args):
        if args[i] == "--llm" and i + 1 < len(args): llm_url = args[i+1]; i += 2
        elif args[i] == "--model" and i + 1 < len(args): model = args[i+1]; i += 2
        else: i += 1
    graph_data = _json.loads(graph_path.read_text())
    result = extract_domains(graph_data, llm_url, model)
    print(format_domains(result))
    # Save
    out = Path(".codemap-output/domain-graph.json")
    out.write_text(_json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n  {C.BGREEN}✓{C.RST} {C.GREEN}Saved to {out}{C.RST}")


def _run_chat(args):
    """Handle: steercode chat --llm URL [question]"""
    llm_url = ""
    model = ""
    question = None
    i = 0
    while i < len(args):
        if args[i] == "--llm" and i + 1 < len(args): llm_url = args[i+1]; i += 2
        elif args[i] == "--model" and i + 1 < len(args): model = args[i+1]; i += 2
        else: question = " ".join(args[i:]); break
    if not llm_url:
        saved = load_config()
        llm_url = saved.get("llm_url", "")
    if not llm_url:
        print(f"  {C.RED}✗ Chat requires LLM. Use: steercode chat --llm URL \"question\"{C.RST}"); return
    graph_path = Path(".codemap-output/knowledge-graph.json")
    if not graph_path.exists():
        print(f"{C.RED}  ✗ No knowledge graph. Run 'python steercode.py .' first.{C.RST}"); sys.exit(1)
    from src.chat import ChatSession
    session = ChatSession(str(graph_path), llm_url, model)
    if question:
        answer = session.ask(question)
        print(f"\n  {answer}\n")
        return
    # Interactive REPL
    print(f"  {C.BGREEN}SteerCode Chat{C.RST} {C.DIM}(type 'exit' to quit){C.RST}\n")
    while True:
        try:
            q = input(f"  {C.BGREEN}>{C.RST} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if not q or q.lower() in ("exit", "quit"): break
        print(f"  {C.DIM}Thinking...{C.RST}")
        answer = session.ask(q)
        print(f"\n  {answer}\n")


def _run_explain(args):
    """Handle: steercode explain <name>"""
    if not args:
        print(f"  Usage: steercode explain <function_or_class_name>"); return
    from src.query import GraphQuery
    graph_path = Path(".codemap-output/knowledge-graph.json")
    if not graph_path.exists():
        print(f"{C.RED}  ✗ No knowledge graph. Run 'python steercode.py .' first.{C.RST}"); sys.exit(1)
    q = GraphQuery(str(graph_path))
    info = q.explain(args[0], root=Path("."))
    if not info:
        print(f"  {C.YELLOW}Node not found: {args[0]}{C.RST}"); return
    # Format
    print(f"\n  {C.BGREEN}{'═' * 50}{C.RST}")
    print(f"  {C.WHITE}{C.BOLD}{info['name']}{C.RST}")
    print(f"  {C.DIM}File: {info['file']}  Lines: {info.get('line_range', '')}{C.RST}")
    meta = []
    if info.get("type"): meta.append(info["type"])
    if info.get("complexity"): meta.append(info["complexity"])
    if info.get("domain"): meta.append(f"[{info['domain']}]")
    if info.get("role"): meta.append(info["role"])
    if meta: print(f"  {C.GREEN}{' · '.join(meta)}{C.RST}")
    if info.get("effects"): print(f"  {C.GREEN}Effects: {', '.join(info['effects'])}{C.RST}")
    if info.get("summary"): print(f"\n  {info['summary']}")
    if info.get("callers"):
        print(f"\n  {C.WHITE}Called by:{C.RST}")
        for c in info["callers"][:10]: print(f"    → {C.GREEN}{c}{C.RST}")
    if info.get("callees"):
        print(f"\n  {C.WHITE}Calls:{C.RST}")
        for c in info["callees"][:10]: print(f"    → {C.GREEN}{c}{C.RST}")
    if info.get("source"):
        print(f"\n  {C.WHITE}Source:{C.RST}")
        for num, line in info["source"][:30]:
            print(f"  {C.DIM}{num:4d}{C.RST} │ {line}")
        if len(info["source"]) > 30:
            print(f"  {C.DIM}     ... ({len(info['source']) - 30} more lines){C.RST}")
    print()


def _run_onboard():
    """Handle: steercode onboard"""
    import json as _json
    from src.onboard import generate_onboard
    graph_path = Path(".codemap-output/knowledge-graph.json")
    if not graph_path.exists():
        print(f"{C.RED}  ✗ No knowledge graph. Run 'python steercode.py .' first.{C.RST}"); sys.exit(1)
    graph_data = _json.loads(graph_path.read_text())
    out = generate_onboard(graph_data, Path("."))
    print(f"  {C.BGREEN}✓{C.RST} {C.GREEN}Onboarding guide saved to {out}{C.RST}")


def _run_diff(args):
    """Handle: steercode diff [ref]"""
    import json as _json
    from src.diff import get_changed_files, analyze_diff, format_diff
    graph_path = Path(".codemap-output/knowledge-graph.json")
    if not graph_path.exists():
        print(f"{C.RED}  ✗ No knowledge graph. Run 'python steercode.py .' first.{C.RST}"); sys.exit(1)
    graph_data = _json.loads(graph_path.read_text())
    ref = args[0] if args else None
    changed = get_changed_files(Path("."), ref)
    if not changed:
        print(f"  {C.GREEN}No changes detected.{C.RST}"); return
    result = analyze_diff(graph_data, changed)
    print(format_diff(result))


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "query":
        _run_query(sys.argv[2:])
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "diff":
        _run_diff(sys.argv[2:])
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "onboard":
        _run_onboard()
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "explain":
        _run_explain(sys.argv[2:])
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "chat":
        _run_chat(sys.argv[2:])
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "domain":
        _run_domain(sys.argv[2:])
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "tour":
        _run_tour(sys.argv[2:])
        return

    if len(sys.argv) == 1:
        cfg = interactive_setup()
        class Args: pass
        args = Args()
        for k, v in cfg.items(): setattr(args, k, v)
    else:
        args = _parse_args()

    root = Path(" ".join(args.path)).resolve()
    if not root.is_dir():
        print(f"{C.RED}  ✗ Error: {root} is not a directory{C.RST}"); sys.exit(1)

    output_dir = (root / args.output) if not Path(args.output).is_absolute() else Path(args.output)
    llm_url = getattr(args, "llm", "")
    use_llm = bool(llm_url)

    banner()
    print(f"  {C.WHITE}Project:{C.RST}  {C.BOLD}{root.name}{C.RST}")
    print(f"  {C.WHITE}Path:{C.RST}     {C.DIM}{root}{C.RST}")
    if use_llm:
        print(f"  {C.WHITE}LLM:{C.RST}      {C.MAGENTA}{llm_url}{C.RST}")
    print()

    _run_pipeline(args, root, output_dir, llm_url, use_llm)

if __name__ == "__main__":
    main()
