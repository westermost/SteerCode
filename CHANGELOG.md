# Changelog

## v1.1.0 — 6 New Commands

### Diff Analysis
- `steercode diff [ref]` — map git changes to knowledge graph
- 1-hop impact expansion via calls/imports edges
- Risk scoring: HIGH (orchestrator/external_api), MEDIUM (data_access/db_write), LOW

### Onboarding Guide
- `steercode onboard` — generate docs/ONBOARDING.md
- Overview table, architecture layers, key components, complexity hotspots, reading order

### Explain with Source
- `steercode explain <name>` — deep-dive with source code + line numbers
- Shows metadata, callers, callees, and actual source code

### Chat Mode
- `steercode chat --llm URL [question]` — interactive Q&A about codebase
- Searches graph by keywords, expands 1-hop, sends context to LLM
- Single question or interactive REPL mode

### Domain Extraction
- `steercode domain [--llm URL]` — extract business domains and flows
- Groups nodes by domain_hint, traces call chains from entry points
- Saves domain-graph.json

### Guided Tours
- `steercode tour [--focus domain]` — learning path ordered by dependency
- Topological sort by layer (Data → Service → API → UI)
- Group by directory, highlight key files

## v1.0.0 — Code Intelligence Engine

### Performance (critical fixes)
- `compute_importance()`: O(N×E) → O(N+E) via adjacency map (20min → 0.2s for 80K edges)
- Semantic extraction: per-function → per-file (267s → 3s for 20K functions)
- Fingerprints: MD5 content hash → size+mtime stat (30s → 0.5s for 20K files)
- Scan progress: throttled to every 50 files (avoid I/O bottleneck)
- Force unbuffered stdout + Windows ANSI escape support
- Speed display: `25s/batch` instead of `0.0/s` when rate < 1

### Rich Auto-Summaries (no LLM)
- Generate summaries from semantic info: `Function (userId, amount) · orchestrator · [payment] · → external_api:stripe`

### Incremental Fix
- Don't skip when `--llm` provided on unchanged files (allow LLM enrichment after non-LLM run)

### Query Engine
- `steercode query find` — O(1) indexed lookup by domain, effect, role, type, name
- `steercode query impact <name>` — bounded BFS impact analysis (depth=2)
- `steercode query flow <from> <to>` — shortest execution path via BFS
- `steercode query explain <name>` — full context: summary, callers, callees, effects

### MCP Server
- `src/mcp_server.py` — stdio JSON-RPC 2.0 transport
- 4 tools: `steercode_find`, `steercode_impact`, `steercode_flow`, `steercode_explain`
- Compatible with Kiro, Cursor, Claude Code, and any MCP client

## v0.4.0 — Production Ready

### Concurrent Enrichment
- ThreadPoolExecutor with max_workers=3, thread-safe progress bar
- Sequential retry with backoff for failed batches

### Incremental Updates
- File fingerprinting (MD5) saved to `fingerprints.json`
- `--full` flag to force rebuild
- Bounded BFS impact expansion (follows `calls`/`imports`, max depth=2)
- `merge_graphs()` for incremental graph updates

### Evaluation
- `tests/eval.py` with golden test framework (5 tests, baseline: 0.95)

## v0.3.0 — Graph Compression

### 3-Level Summaries
- `enrich_files()` — function summaries → file summary
- `enrich_modules()` — file summaries → module summary
- `detect_modules()` — group files by top-level directory

### Fact Anchoring
- Prompt forces LLM to preserve `external_apis`, `db_tables`, `domains`
- `merge_facts()` — deduplicate across levels
- `_verify_facts()` — loss check, force-merge dropped facts

## v0.2.0 — Smart Analysis

### Semantic Extraction
- `SideEffect` with confidence + source tagging (`regex`/`import_inference`)
- 5 side effect detectors: db_write, db_read, external_api, file_io, state_mutate
- 7 business domains, 5 execution roles, 4 control flow types
- Entity extraction + normalization (`StripeGateway` → `stripe`)

### Structured Batch
- `<FUNC id="fN">` prompt format with semantic metadata
- Batch by file (10-20 files/batch)
- `validate_and_retry()` for missing IDs

### Deep Context
- Caller/callee injection sorted by importance
- `compute_importance()` with decay + percentile normalization

### Reliability & Observability
- `classify_error()` — timeout, rate_limit, auth
- Batch cache for idempotent re-runs
- Per-batch metrics saved to `metrics.json`

## v0.1.1

### Bug Fixes
- Simplify LLM enrichment process by removing concurrency and enhancing error handling

## v0.1.0

### Features
- Optimize Go module detection and update Docker base image key
- Correct regex patterns for JavaScript and TypeScript branch detection
- Enhance LLM integration and version detection
- Refactor graph building and parsing logic
- Add output generation for dashboard and steering files

### Initial (v0.0.1)
- Core file scanner (20+ languages, .gitignore support)
- Multi-language parser (Python AST + regex for 14 languages)
- Knowledge graph builder with cross-reference calls
- Architectural layer detection (7 layers)
- Complexity analysis (cyclomatic + cognitive + 11 framework rules)
- Version detection (PHP, Node, Python, Go, Ruby, Docker)
- Interactive HTML dashboard (vis-network, 5 languages)
- Progressive disclosure — per-layer chunks
- Steering files for 7 AI tools
- Matrix hacker green terminal theme
- Interactive wizard + settings persistence
