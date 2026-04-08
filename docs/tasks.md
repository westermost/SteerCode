# SteerCode v0.2 — Task List

## v0.2: Smart Analysis

### Phase 1: Semantic Extraction
- [ ] 1.1 Add `SideEffect`, `SemanticInfo` to `src/types.py`
- [ ] 1.2 Implement `SIDE_EFFECT_PATTERNS` regex detector in `src/parser.py`
- [ ] 1.3 Implement `DOMAIN_KEYWORDS` matcher in `src/parser.py`
- [ ] 1.4 Implement `ROLE_PATTERNS` matcher in `src/parser.py`
- [ ] 1.5 Implement `CONTROL_FLOW_PATTERNS` detector in `src/parser.py`
- [ ] 1.6 Implement `extract_entity()` with import inference in `src/parser.py`
- [ ] 1.7 Add `ENTITY_ALIASES` + `normalize_entity()` in `src/parser.py`
- [ ] 1.8 Wire `extract_semantics()` into `parse_file()` output
- [ ] 1.9 Store semantic data in graph nodes via `src/graph.py`
- [ ] 1.10 Test: verify semantic fields on real PHP/JS/Python project

### Phase 2: Structured Batch + Validation
- [ ] 2.1 Rebuild prompt format with `<FUNC id="">` structure in `src/llm.py`
- [ ] 2.2 Include semantic metadata (side_effects, domain, role) in prompt
- [ ] 2.3 Batch by file (10-20 files/batch) instead of per-node
- [ ] 2.4 Implement `validate_and_retry()` — check missing IDs, retry
- [ ] 2.5 Test: verify all IDs returned, retry works on partial output

### Phase 3: Deep Context Prompt
- [ ] 3.1 Export caller/callee relationships from `src/graph.py`
- [ ] 3.2 Implement `select_context()` with TOP_K prioritization
- [ ] 3.3 Inject execution flow + neighbor summaries into prompt
- [ ] 3.4 Test: compare summary quality with/without context

### Importance Scoring
- [ ] 3.5 Implement `compute_importance()` with decay in `src/graph.py`
- [ ] 3.6 Normalize scores by percentile
- [ ] 3.7 Store importance in graph nodes
- [ ] 3.8 Use importance for context selection in Phase 3

### Reliability
- [ ] 3.9 Implement `classify_error()` with ERROR_HANDLERS in `src/llm.py`
- [ ] 3.10 Implement batch cache (idempotency) — `get_batch_id()`, cache dir
- [ ] 3.11 Skip cached batches on re-run

### Observability
- [ ] 3.12 Create `src/metrics.py` with `BatchMetric`, `RunMetrics`
- [ ] 3.13 Log metrics per batch in `src/llm.py`
- [ ] 3.14 Save `metrics.json` to output dir
- [ ] 3.15 Display summary stats in terminal after enrichment

### Integration
- [ ] 3.16 Update `src/dashboard.py` — steering includes semantic fields
- [ ] 3.17 Update `dashboard_template.html` — show domain, role, side_effects in detail panel
- [ ] 3.18 Update README with v0.2 features
- [ ] 3.19 Full test on 3 real projects (PHP, JS/TS, Python)
- [ ] 3.20 Commit + release v0.2

---

## v0.3: Graph Compression

- [ ] 4.1 Implement `enrich_files()` — aggregate function summaries → file summary
- [ ] 4.2 Implement `enrich_modules()` — aggregate file summaries → module summary
- [ ] 4.3 Implement fact anchoring prompt (MUST preserve external_apis, db_tables)
- [ ] 4.4 Implement `merge_facts()` with confidence
- [ ] 4.5 Implement `verify_compression()` — loss check + retry
- [ ] 4.6 Implement `detect_modules()` — group files by directory
- [ ] 4.7 Add `FileSummary`, `ModuleSummary` to `src/types.py`
- [ ] 4.8 Update steering to use multi-level summaries
- [ ] 4.9 Test: verify facts preserved across 3 levels
- [ ] 4.10 Commit + release v0.3

---

## v0.4: Production Ready

### Concurrent
- [ ] 5.1 Wrap enrichment in `ThreadPoolExecutor` (max_workers=3)
- [ ] 5.2 Sequential retry with exponential backoff for failed batches
- [ ] 5.3 Thread-safe progress bar
- [ ] 5.4 Test: verify no race conditions, metrics correct

### Incremental
- [ ] 6.1 Implement `compute_fingerprints()` in `src/scanner.py`
- [ ] 6.2 Implement `diff_fingerprints()` — detect changed files
- [ ] 6.3 Implement `get_impacted_files()` — bounded BFS (max_depth=2)
- [ ] 6.4 Implement `merge_graphs()` — merge new results into existing graph
- [ ] 6.5 Add `--full` flag to force rebuild
- [ ] 6.6 Save/load `fingerprints.json`
- [ ] 6.7 Test: modify 1 file, verify only impacted nodes re-processed

### Evaluation
- [ ] 6.8 Create `tests/eval.py` with golden test set
- [ ] 6.9 Implement `eval_summary()` + `eval_graph()`
- [ ] 6.10 Run eval, establish baseline scores
- [ ] 6.11 Commit + release v0.4

---

## v1.0: Code Intelligence Engine

- [ ] 7.1 Create `src/query.py` with `GraphQuery` class
- [ ] 7.2 Implement `find()` with indexed lookup
- [ ] 7.3 Implement `impact()` — bounded BFS from node
- [ ] 7.4 Implement `flow()` — trace execution path
- [ ] 7.5 Implement `explain()` — full node context
- [ ] 7.6 Add `steercode query "..."` CLI command
- [ ] 7.7 Create MCP server (`src/mcp_server.py`)
- [ ] 7.8 Test with Kiro + Cursor MCP integration
- [ ] 7.9 Release v1.0
