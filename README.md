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

# Generate steering for specific AI tools only
python steercode.py . --tools kiro,cursor

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
3. **Analyzes** complexity with language-aware and framework-aware rules
4. **Builds** a knowledge graph with nodes, edges, and architectural layers
5. **Generates**:
   - `.codemap-output/knowledge-graph.json` — structured graph for AI tools
   - `.codemap-output/dashboard.html` — interactive visual explorer (multi-language)
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

Use `--tools` to generate only the ones you need:
```bash
python steercode.py . --tools kiro,cursor       # Only Kiro + Cursor
python steercode.py . --tools claude,copilot     # Only Claude Code + Copilot
```

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

## Complexity Analysis

SteerCode uses a production-grade, language-aware complexity scoring system that goes beyond simple line counting.

**Scoring factors:**
- **Cyclomatic complexity** — branch/control-flow patterns per language (16 languages)
- **Nesting depth** — exponentially weighted
- **Cognitive load** — recursion, callbacks, ternary operators
- **Framework signals** — framework-specific patterns that indicate complexity
- **Parameter count** — penalty for functions with 4+ parameters
- **Size** — logarithmic (200 lines ≠ 10x harder than 20)

**Framework-aware rules:**

| Framework | Signals detected |
|---|---|
| React | hooks, useEffect deps, callbacks |
| Django | ORM queries, Q objects, views |
| Spring | annotations, DI, transactions |
| Laravel | Eloquent chains, Facades, Middleware |
| Express | routes, async/await patterns |
| Rails | ActiveRecord, scopes, chained queries |
| Stimulus | outlets, targets, dispatch, lifecycle |
| Symfony 2.x | service locator, Doctrine, voters, compiler passes |
| PHP 5.x legacy | globals, magic methods, eval, deprecated functions |
| TypeScript types | conditional types, infer, mapped types, generics |

Adding a new framework rule is simple — just create a file in `src/complexity/rules/`:
```python
# src/complexity/rules/my_framework.py
from .. import register_rules

register_rules(
    frameworks={"my_framework": [
        (r'pattern_to_match', weight),
    ]},
    hints={"my_framework": r'detection_pattern'},
)
```

## Dashboard Features

- **Interactive graph** — drag, zoom, click nodes (vis-network)
- **Click-to-expand** — large graphs load connections on demand
- **Search** — fuzzy search across all nodes (Ctrl+K)
- **Layer filtering** — API, UI, Service, Data, Infrastructure, Tests, Docs
- **Type filtering** — show/hide files, functions, classes
- **Complexity filtering** — show/hide simple, moderate, complex nodes
- **Language filtering** — filter by programming language
- **Node limit** — adjustable for large codebases
- **Detail panel** — summary, connections, tags, complexity
- **Multi-language UI** — English, 한국어, 中文, 日本語, Español
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

LLM enrichment covers file, function, and class nodes — prioritized by complexity.

## Project Structure

```
steercode.py                  # CLI entry point
src/
├── __init__.py               # Public API
├── types.py                  # Data classes (GraphNode, GraphEdge, Layer)
├── scanner.py                # File scanning & .gitignore
├── graph.py                  # Knowledge graph builder
├── llm.py                    # LLM enrichment
├── ui.py                     # Terminal UI helpers
├── complexity/               # Complexity analysis engine
│   ├── __init__.py           # Engine + auto-discovery
│   └── rules/                # Drop a .py file here to add rules
│       ├── languages.py      # Branch patterns (16 languages)
│       ├── react.py          # React rules
│       ├── django.py         # Django rules
│       ├── spring.py         # Spring rules
│       ├── laravel.py        # Laravel rules
│       ├── express.py        # Express rules
│       ├── rails.py          # Rails rules
│       ├── stimulus.py       # Stimulus rules
│       ├── symfony.py        # Symfony 2.x rules
│       ├── php5.py           # PHP 5.x legacy rules
│       └── typescript_types.py  # TypeScript type system rules
├── parsers/                  # Language parsers
│   ├── __init__.py           # parse_file() dispatcher
│   ├── python_parser.py      # Python AST parser
│   └── regex_parser.py       # Regex parser (JS, Java, Go, etc.)
└── output/                   # Output generation
    ├── __init__.py
    ├── dashboard.py          # HTML dashboard assembly
    └── steering.py           # AI steering files
dashboard/
├── template.html             # HTML structure
├── style.css                 # Styles
├── app.js                    # Dashboard logic
└── i18n.js                   # Translations (EN, KO, ZH, JA, ES)
```

## Contributing

**Add a complexity rule:** Create a file in `src/complexity/rules/` — auto-discovered at runtime.

**Add a language parser:** Create a file in `src/parsers/` and register in `src/parsers/__init__.py`.

**Add a dashboard translation:** Add a locale block in `dashboard/i18n.js` and an `<option>` in `dashboard/template.html`.

**Add a steering target:** Add an entry to `STEERING_TARGETS` in `src/output/steering.py`.

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
  --tools LIST           Comma-separated AI tools (kiro,cursor,copilot,claude,windsurf,cline,codex)
  --no-open              Don't open dashboard in browser
  --json-only            Only output JSON, skip dashboard
```

## License

MIT
