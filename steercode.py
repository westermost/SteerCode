#!/usr/bin/env python3
"""SteerCode — Scan your codebase. Steer your AI."""

import json, os, sys, webbrowser
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

from src import (
    scan_files, detect_language, build_graph, detect_layers,
    enrich_with_llm, generate_dashboard, generate_steering,
    detect_versions,
    C, banner, phase_header, phase_done, table, summary_box, prompt,
    TOOL_NAMES,
)

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
    files = scan_files(root)
    if not files:
        print(f"  {C.YELLOW}  ⚠ No supported files found.{C.RST}"); sys.exit(0)
    lang_counts = defaultdict(int)
    for f in files: lang_counts[detect_language(f)] += 1
    t1 = time.time()
    phase_done(f"{len(files):,} files across {len(lang_counts)} languages", t1 - t0)
    table([(l, f"{c:,}") for l, c in sorted(lang_counts.items(), key=lambda x: -x[1])[:8]])
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
            llm_url, args.model, getattr(args, "context_size", 8192), getattr(args, "max_enrich", 0))
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


def main():
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
