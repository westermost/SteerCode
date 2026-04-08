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
Codebase → Scan → Parse → Semantic Analysis → Knowledge Graph → Dashboard + Steering
                                                                       ↓
                                                                 AI writes better code
```

1. **Scans** your codebase (respects `.gitignore`, auto-adds output to `.gitignore`)
2. **Parses** functions, classes, imports across 20+ languages
3. **Extracts semantics** — side effects, business domain, execution role, control flow
4. **Scores importance** — percentile-ranked by callers, side effects, role
5. **Detects** runtime versions, frameworks, and dependencies
6. **Analyzes** complexity with language-aware and framework-aware rules
7. **Builds** a knowledge graph with nodes, edges, and architectural layers
8. **Generates**:
   - `.codemap-output/knowledge-graph.json` — full graph for dashboard
   - `.codemap-output/graph-index.json` — layer index for AI progressive loading
   - `.codemap-output/layers/*.json` — per-layer chunks (fit any context window)
   - `.codemap-output/dashboard.html` — interactive visual explorer (5 languages)
   - Steering files for **7 AI tools** (Kiro, Cursor, Copilot, Claude Code, Windsurf, Cline, Codex)

## Output

```
.codemap-output/
  knowledge-graph.json         # Full graph (nodes, edges, layers)
  knowledge-graph.compact.json # Columnar format for AI (smaller)
  graph-index.json             # Layer index — AI reads this first
  layers/                      # Per-layer chunks for progressive loading
    service_1.json             #   AI loads only what it needs
    data_1.json
    api_1.json
    cross_layer.json           #   Cross-layer dependencies
  dashboard.html               # Interactive dashboard (open in browser)
  data.js                      # Dashboard data
  steering/                    # Steering files for root-level AI tools
    CLAUDE.md                  #   Claude Code (copy to project root)
    AGENTS.md                  #   Codex
    .windsurfrules             #   Windsurf
    .clinerules                #   Cline

# Auto-placed steering (detected automatically by these tools)
.kiro/steering/knowledge-graph.md    # Kiro
.cursor/rules/knowledge-graph.md     # Cursor
.github/copilot-instructions.md      # GitHub Copilot
```

## Progressive Disclosure — Solving the Context Window Problem

Large projects produce large graphs. A 57K-node project generates a 21MB JSON (~5.4M tokens) — far exceeding any model's context window.

**SteerCode splits the graph into layer chunks that AI agents load on demand:**

```
graph-index.json          ← AI reads first (~2K tokens)
layers/
  service_1.json          ← Load when working on business logic
  data_1.json             ← Load when working on models/DB
  api_1.json              ← Load when working on routes
  cross_layer.json        ← Load to trace cross-layer deps
```

| Approach | Tokens | Fits 1M context? |
|---|---|---|
| Full JSON | ~5,460,000 | ❌ |
| Index + 2 layers + cross | ~830,000 | ✅ |
| Index only | ~2,000 | ✅ |

Large layers are recursively chunked by directory structure until each chunk fits comfortably in context (~200K tokens max).

**Compression techniques (100% data preserved):**
- Path indexing — file paths → numeric index
- Columnar format — field names appear once
- Type/complexity as single chars (`F/f/C`, `!/~`)
- Edges by name instead of hash IDs
- Default summaries stripped to empty string

## Version Detection

Automatically detects runtime versions, frameworks, and packages from config files:

```yaml
runtime:
  php: 5.6
  node: 16.16.0
  go: 1.20
  ruby: 2.5.9
  docker_base: amazonlinux:2.0.20180827
frameworks:
  Symfony: 2.0.4
  Sinatra: 2.0.0
packages:
  composer: 8 packages
  npm: 55 packages
  gem: 43 packages
```

Scans: `composer.json`, `package.json`, `go.mod`, `Gemfile`, `.ruby-version`, `.node-version`, `Dockerfile`, `pyproject.toml`, `requirements.txt`, `Cargo.toml`

Supports monorepos (scans root + 1 level subdirs). With `--llm`, also analyzes `pom.xml`, `build.gradle`, `docker-compose.yml`.

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

## Supported Languages

| Full AST Parsing | Regex-based Parsing |
|---|---|
| Python | JavaScript, TypeScript, Java, Go, Rust, C/C++, C#, Ruby, PHP, Kotlin, Swift, Scala, Lua, Shell |

Also detects: JSON, YAML, TOML, HTML, CSS/SCSS, SQL, Markdown, Dockerfile, Terraform, Protobuf, GraphQL, Vue, Twig, Blade

## Complexity Analysis

Production-grade, language-aware complexity scoring beyond simple line counting.

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

Adding a new framework rule:
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
- **Isolated node hiding** — nodes without connections hidden until searched
- **Search** — fuzzy search across all nodes (Ctrl+K)
- **Layer filtering** — API, UI, Service, Data, Infrastructure, Tests, Docs
- **Type filtering** — show/hide files, functions, classes
- **Complexity filtering** — show/hide simple, moderate, complex nodes
- **Language filtering** — filter by programming language
- **Node limit** — adjustable for large codebases
- **Detail panel** — summary, connections, tags, complexity
- **Multi-language UI** — English, 한국어, 中文, 日本語, Español
- **Dark theme**

## Semantic Analysis (v0.2)

Every function and class is analyzed for semantic signals — no LLM required:

| Signal | Detection | Example |
|---|---|---|
| **Side effects** | Regex + import inference | `db_write:transactions`, `external_api:stripe` |
| **Business domain** | Keyword matching | `payment`, `auth`, `user`, `email`, `storage` |
| **Execution role** | Name + path patterns | `entry_point`, `orchestrator`, `validator`, `data_access`, `adapter` |
| **Control flow** | Pattern detection | `branching`, `loop`, `try_catch`, `async` |
| **Importance** | Graph analysis | Percentile score from callers, side effects, role, complexity |

Side effects include confidence scores and source tagging (`regex` vs `import_inference`), with entity-level granularity (e.g. `external_api:stripe` not just `external_api`).

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

**LLM enrichment features:**
- **Structured batch** — `<FUNC id="fN">` format with semantic metadata, 10-20 files per batch
- **Context-aware prompts** — callers, callees, importance scores injected into prompt
- **Output validation** — checks all IDs returned, retries missing ones
- **Batch cache** — idempotent, skips already-enriched batches on re-run
- **Error classification** — timeout, rate_limit, auth, with appropriate retry strategy
- **Metrics** — per-batch latency, success rate, token estimates saved to `metrics.json`
- Retry with adaptive timeout (300s → 450s → 675s)
- ETA countdown with rolling average speed
- Smart skip: test files, config files, vendored libraries
- Priority: complex nodes first, simple last

## Tested On

| Project | Language | Nodes | Edges | Layers | Chunks | Max Chunk | Versions |
|---|---|---|---|---|---|---|---|
| SteerCode | Python/JS | 133 | 155 | 3 | 3 | 2.4K tok | — |
| homes-pc | PHP/JS | 56,942 | 88,410 | 7 | 81 | 173K tok | PHP 5.6, Symfony 2.0.4 |
| homes-sp | PHP/JS | 12,614 | 18,389 | 7 | 7 | 180K tok | PHP 7.2, Symfony 3.4.6 |
| API-Server | Ruby | 50,468 | 62,111 | 7 | 76 | 151K tok | Ruby 2.5.9, Sinatra 2.0.0 |
| v4-bunjou | PHP/JS | 9,312 | 14,687 | 6 | 9 | 35K tok | Legacy (no composer) |

All projects: max chunk < 200K tokens, fits 1M context window.

## Project Structure

```
steercode.py                  # CLI entry point
src/
├── __init__.py               # Public API
├── types.py                  # Data classes (GraphNode, GraphEdge, Layer)
├── scanner.py                # File scanning & .gitignore
├── graph.py                  # Knowledge graph builder + layer detection
├── llm.py                    # LLM enrichment (retry, concurrent, ETA)
├── versions.py               # Version detection (monorepo support)
├── ui.py                     # Terminal UI + ETATracker
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
│   ├── regex_parser.py       # Regex parser (JS, Java, Go, etc.)
│   └── semantics.py          # Semantic extraction (side effects, domain, role)
└── output/                   # Output generation
    ├── __init__.py
    ├── dashboard.py          # Dashboard + progressive disclosure
    └── steering.py           # AI steering files (7 tools)
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
- **Versions** tell AI which syntax and APIs are safe to use
- **Steering file** instructs AI to check the graph before making changes
- **Progressive loading** lets AI work with codebases of any size
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
