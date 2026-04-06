# 🔍 SteerCode

**Scan your codebase. Steer your AI.**

A zero-dependency Python tool that scans any codebase, builds a knowledge graph, and generates AI steering files — so your AI coding assistant understands your project before writing a single line.

## Quick Start

```bash
# Analyze current directory
python steercode.py .

# Analyze a specific project
python steercode.py /path/to/project

# With local LLM for smart summaries (LM Studio / Ollama)
python steercode.py . --llm http://localhost:1234

# Interactive mode (guided wizard)
python steercode.py
```

## What It Does

```
Codebase → Scan → Parse → Knowledge Graph → Dashboard + Steering
                                                         ↓
                                                   AI writes better code
```

1. **Scans** your codebase (respects `.gitignore`)
2. **Parses** functions, classes, imports across 20+ languages
3. **Builds** a knowledge graph with nodes, edges, and architectural layers
4. **Generates**:
   - `.codemap-output/knowledge-graph.json` — structured graph for AI tools
   - `.codemap-output/dashboard.html` — interactive visual explorer
   - Steering files for **7 AI tools** (Kiro, Cursor, Copilot, Claude Code, Windsurf, Cline, Codex)

## Output

```
.codemap-output/
  knowledge-graph.json   # Full graph data (nodes, edges, layers)
  dashboard.html         # Interactive dashboard (open in browser)
  data.js                # Dashboard data
  steering/              # Steering files for root-level AI tools
    CLAUDE.md            # Claude Code (copy to project root to activate)
    AGENTS.md            # Codex
    .windsurfrules       # Windsurf
    .clinerules          # Cline

# Auto-placed steering (detected automatically by these tools)
.kiro/steering/knowledge-graph.md    # Kiro
.cursor/rules/knowledge-graph.md     # Cursor
.github/copilot-instructions.md      # GitHub Copilot
```

## Supported AI Tools

| AI Tool | Steering File | Auto-detected |
|---|---|---|
| Kiro | `.kiro/steering/knowledge-graph.md` | ✅ Auto |
| Cursor | `.cursor/rules/knowledge-graph.md` | ✅ Auto |
| GitHub Copilot | `.github/copilot-instructions.md` | ✅ Auto |
| Claude Code | `.codemap-output/steering/CLAUDE.md` | 📋 Copy to root |
| Windsurf | `.codemap-output/steering/.windsurfrules` | 📋 Copy to root |
| Cline | `.codemap-output/steering/.clinerules` | 📋 Copy to root |
| Codex | `.codemap-output/steering/AGENTS.md` | 📋 Copy to root |

For tools that need root placement:
```bash
cp .codemap-output/steering/CLAUDE.md .       # Claude Code
cp .codemap-output/steering/AGENTS.md .       # Codex
cp .codemap-output/steering/.windsurfrules .  # Windsurf
cp .codemap-output/steering/.clinerules .     # Cline
```

## Supported Languages

| Full AST Parsing | Regex-based Parsing |
|---|---|
| Python | JavaScript, TypeScript, Java, Go, Rust, C/C++, C#, Ruby, PHP, Kotlin, Swift, Scala, Lua, Shell |

Also detects: JSON, YAML, TOML, HTML, CSS/SCSS, SQL, Markdown, Dockerfile, Terraform, Protobuf, GraphQL, Vue, Twig, Blade

## Dashboard Features

- **Interactive graph** — drag, zoom, click nodes (vis-network)
- **Click-to-expand** — large graphs load connections on demand
- **Search** — fuzzy search across all nodes (Ctrl+K)
- **Layer filtering** — API, UI, Service, Data, Infrastructure, Tests, Docs
- **Type filtering** — show/hide files, functions, classes
- **Node limit** — adjustable for large codebases
- **Detail panel** — summary, connections, tags, complexity
- **Dark theme**

## Local LLM Support

Optionally connect a local LLM for smart summaries (no cloud API needed):

```bash
# LM Studio (default port 1234)
python steercode.py . --llm http://localhost:1234

# Ollama
python steercode.py . --llm http://localhost:11434

# Custom model and context size
python steercode.py . --llm http://localhost:1234 --model qwen2.5-coder --context-size 8192
```

Compatible with any OpenAI-compatible API: LM Studio, Ollama, LocalAI, vLLM, text-generation-webui.

## Why?

AI coding tools are powerful but blind — they don't know your architecture, your patterns, or which file does what.

SteerCode gives them a map:
- **Knowledge graph** tells AI how files connect, what functions do, which layer they belong to
- **Steering file** instructs AI to check the graph before making changes
- **Dashboard** lets humans explore the same information visually

## Requirements

- Python 3.7+
- No external dependencies (stdlib only)
- Optional: local LLM for smart summaries

## CLI Options

```
python steercode.py [path] [options]

Options:
  -o, --output DIR       Output directory (default: .codemap-output)
  --llm URL              Local LLM URL for smart summaries
  --model NAME           Model name (optional)
  --context-size N       LLM context size in tokens (default: 8192)
  --max-enrich N         Max nodes to enrich with LLM
  --no-open              Don't open dashboard in browser
  --json-only            Only output JSON, skip dashboard
```

## License

MIT
