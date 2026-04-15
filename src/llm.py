"""LLM enrichment — structured batch, validation, context-aware prompts."""

import sys, json, re, time, hashlib, threading, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
from .ui import C, progress_bar_eta, ETATracker
from . import config as cfg

DEFAULT_LLM_URL = "http://localhost:1234/v1/chat/completions"

# ─── HTTP ────────────────────────────────────────────────────────────────────

def _llm_request(url: str, model: str, prompt: str,
                 timeout: int = None, max_retries: int = None) -> str:
    timeout = timeout or cfg.get("llm", "timeout")
    max_retries = max_retries or cfg.get("llm", "max_retries")
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/")
        if url.endswith("/v1/completions"):
            url = url.replace("/v1/completions", "/v1/chat/completions")
        elif not url.endswith("/v1/chat/completions"):
            url = url + "/v1/chat/completions"
    payload = {"max_tokens": 4096, "messages": [
        {"role": "system", "content":
            "You are a senior code analyst. Analyze code for a knowledge graph. "
            "Rules: 1) 1-2 sentences on WHAT it does and WHY. "
            "2) Mention key dependencies, side effects, or patterns. "
            "3) Describe behavior, not syntax. "
            "4) Return ONLY valid JSON, no markdown."},
        {"role": "user", "content": prompt},
    ]}
    if model: payload["model"] = model
    body = json.dumps(payload).encode()

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=int(timeout * (1.5 ** attempt))) as resp:
                data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == max_retries - 1: raise
            time.sleep(2 ** (attempt + 1))
    return ""


def _extract_json(text: str) -> Optional[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try: return json.loads(text)
    except json.JSONDecodeError: pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try: return json.loads(m.group())
        except json.JSONDecodeError: pass
    return None

# ─── Error Classification ────────────────────────────────────────────────────

def classify_error(e: Exception) -> str:
    if isinstance(e, (TimeoutError, OSError)) or "timed out" in str(e): return "timeout"
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 429: return "rate_limit"
        if e.code in (401, 403): return "auth"
    return "unknown"

# ─── Batch Cache (Idempotency) ───────────────────────────────────────────────

def _batch_id(items: list, content_tokens: Optional[List[str]] = None) -> str:
    content = json.dumps({
        "nodes": [(n["id"], n["name"]) for n in items],
        "content_tokens": content_tokens or [],
    }, sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()[:12]

def _get_cached(cache_dir: Optional[Path], bid: str) -> Optional[dict]:
    if not cache_dir: return None
    p = cache_dir / f"{bid}.json"
    if p.exists():
        try: return json.loads(p.read_text())
        except Exception: pass
    return None

def _save_cache(cache_dir: Optional[Path], bid: str, result: dict):
    if not cache_dir: return
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{bid}.json").write_text(json.dumps(result))

# ─── Context Selection ───────────────────────────────────────────────────────

TOP_K_CALLERS = None  # loaded from config
TOP_K_CALLEES = None

def _select_context(node: dict, edges: List[dict], node_by_id: Dict[str, dict],
                    importance: Dict[str, float]) -> str:
    top_callers = cfg.get("llm", "top_k_callers")
    top_callees = cfg.get("llm", "top_k_callees")
    """Build context string for a node: callers + callees sorted by importance."""
    nid = node["id"]
    callers = [e["source"] for e in edges if e["target"] == nid and e["type"] == "calls"]
    callees = [e["target"] for e in edges if e["source"] == nid and e["type"] == "calls"]

    callers = sorted(callers, key=lambda x: importance.get(x, 0), reverse=True)[:top_callers]
    callees = sorted(callees, key=lambda x: importance.get(x, 0), reverse=True)[:top_callees]

    parts = []
    if callers:
        lines = []
        for cid in callers:
            cn = node_by_id.get(cid)
            if cn: lines.append(f"  - {cn['name']}: {cn.get('summary', '')[:80]}")
        if lines: parts.append("Called by:\n" + "\n".join(lines))
    if callees:
        lines = []
        for cid in callees:
            cn = node_by_id.get(cid)
            if cn: lines.append(f"  - {cn['name']}: {cn.get('summary', '')[:80]}")
        if lines: parts.append("Calls:\n" + "\n".join(lines))
    return "\n".join(parts)


# ─── Structured Prompt Builder ───────────────────────────────────────────────

def _build_func_block(node: dict, snippet: str, idx: int) -> str:
    """Build <FUNC id="fN"> block with semantic metadata."""
    sem = node.get("semantics", {})
    fid = f"f{idx}"
    parts = [f'<FUNC id="{fid}" file="{Path(node["file_path"]).name}"']
    if sem.get("domain_hint"): parts[0] += f' domain="{sem["domain_hint"]}"'
    if sem.get("execution_role"): parts[0] += f' role="{sem["execution_role"]}"'
    parts[0] += ">"

    parts.append(f"Name: {node['name']}")
    lr = node.get("line_range", [0, 0])
    lines = lr[1] - lr[0] + 1 if lr[1] > lr[0] else 0
    comp = node.get("complexity", "simple")
    if lines: parts.append(f"Lines: {lr[0]}-{lr[1]} ({lines} lines, {comp})")

    effects = sem.get("side_effects", [])
    if effects:
        eff_str = ", ".join(f"{e['type']} ({e['confidence']:.1f})" for e in effects)
        parts.append(f"Side effects: {eff_str}")

    cf = sem.get("control_flow", [])
    if cf: parts.append(f"Control flow: {', '.join(cf)}")

    parts.append(f"Code:\n{snippet}")
    parts.append("</FUNC>")
    return "\n".join(parts)


def _build_batch_prompt(batch_nodes: List[dict], file_contents: Dict[str, list],
                        max_code_chars: int, edges: List[dict] = None,
                        node_by_id: Dict[str, dict] = None,
                        importance: Dict[str, float] = None) -> Tuple[str, List[str], Dict[str, str], List[dict], List[dict], List[str]]:
    """Build structured prompt for a batch.

    Returns (prompt, expected_ids, id_to_node_id, included_nodes, remaining_nodes, content_tokens).
    """
    blocks = []
    expected_ids = []
    id_map = {}  # fN → node["id"]
    total_chars = 0
    included_nodes = []
    remaining_nodes = []
    content_tokens = []
    overflow_started = False

    for n in batch_nodes:
        if overflow_started:
            remaining_nodes.append(n)
            continue
        lines = file_contents.get(n["file_path"])
        if lines is None:
            continue
        s, e = max(0, n["line_range"][0] - 2), min(len(lines), n["line_range"][1] + 1)
        snippet = "\n".join(lines[s:e])
        if len(snippet) > cfg.get("llm", "snippet_max_chars"): snippet = snippet[:cfg.get("llm", "snippet_max_chars")] + "\n..."
        if total_chars + len(snippet) > max_code_chars and blocks:
            overflow_started = True
            remaining_nodes.append(n)
            continue
        total_chars += len(snippet)

        idx = len(included_nodes)
        fid = f"f{idx}"
        block = _build_func_block(n, snippet, idx)
        # Inject context if available
        if edges and node_by_id and importance:
            ctx = _select_context(n, edges, node_by_id, importance)
            if ctx: block = block.replace("</FUNC>", f"{ctx}\n</FUNC>")
        blocks.append(block)
        expected_ids.append(fid)
        id_map[fid] = n["id"]
        included_nodes.append(n)
        content_tokens.append(f'{n["id"]}:{hashlib.md5(snippet.encode()).hexdigest()[:10]}')

    prompt = (
        "Analyze these functions. Each has an ID. Return a JSON object keyed by ID with 1-2 sentence summaries.\n\n"
        + "\n\n".join(blocks)
        + f'\n\nReturn ONLY: {{"f0": "summary...", "f1": "summary...", ...}}'
    )
    return prompt, expected_ids, id_map, included_nodes, remaining_nodes, content_tokens

# ─── Validation + Retry ─────────────────────────────────────────────────────

def _validate_and_retry(result: Optional[dict], expected_ids: List[str],
                        llm_url: str, model: str, prompt: str) -> dict:
    if not result: return {}
    missing = set(expected_ids) - set(result.keys())
    if not missing: return result
    # One retry for missing IDs
    retry_prompt = f"You missed these IDs: {sorted(missing)}. Complete them.\n\n{prompt}"
    try:
        retry_result = _extract_json(_llm_request(llm_url, model, retry_prompt))
        if retry_result: result.update(retry_result)
    except Exception: pass
    return result

# ─── Main Enrichment ─────────────────────────────────────────────────────────

ENRICH_LANGS = {"python","javascript","typescript","java","go","rust","c","cpp",
                "csharp","ruby","php","swift","kotlin","scala","lua","shell","sql"}
SKIP_PATHS = {"test","tests","spec","specs","__tests__","e2e"}

def enrich_with_llm(nodes, edges, root, llm_url, model='',
                    context_size=8192, max_enrich=0, output_dir=None):
    max_code_chars = min((context_size - 800) * 3, cfg.get('llm', 'max_code_chars'))
    cache_dir = (output_dir / 'cache') if output_dir else None

    enrichable = _filter_enrichable(nodes)
    if not enrichable: return 0
    _log_skipped(nodes)
    enrichable = _sort_by_priority(enrichable, max_enrich)
    file_contents = _load_file_contents(enrichable, root)
    batches = _build_batches(enrichable)
    node_by_id = {n['id']: n for n in nodes}
    importance = _compute_and_store_importance(nodes, edges, node_by_id, len(batches))
    enriched, metrics = _run_concurrent(batches, file_contents, max_code_chars, edges,
                                        node_by_id, importance, llm_url, model, cache_dir)
    del file_contents
    if output_dir and metrics:
        try:
            (output_dir / 'metrics.json').write_text(json.dumps({
                'total_batches': len(batches), 'enriched': enriched,
                'batches': metrics}, indent=2))
        except Exception: pass
    return enriched


def _filter_enrichable(nodes):
    return [n for n in nodes if n['type'] in ('function', 'class')
            and n.get('file_path') and n.get('language', '') in ENRICH_LANGS
            and not (SKIP_PATHS & set(n['file_path'].lower().split('/')))]


def _log_skipped(nodes):
    skipped_fe = sum(1 for n in nodes if n['type'] in ('function', 'class')
                     and n.get('language', '') in {'css','html','markdown','json','yaml','toml','xml','dockerfile','terraform','makefile'})
    skipped_test = sum(1 for n in nodes if n['type'] in ('function', 'class')
                       and n.get('file_path') and (SKIP_PATHS & set(n['file_path'].lower().split('/'))))
    if skipped_fe or skipped_test:
        sys.stdout.write(f"\n    {C.DIM}Skipping {skipped_fe} config/frontend + {skipped_test} test nodes{C.RST}\n")


def _sort_by_priority(enrichable, max_enrich):
    comp = {'complex': 3, 'moderate': 2, 'simple': 1}
    tp = {'class': 2, 'function': 1}
    enrichable.sort(key=lambda n: (comp.get(n.get('complexity'), 0), tp.get(n['type'], 0)), reverse=True)
    if max_enrich > 0: enrichable = enrichable[:max_enrich]
    sys.stdout.write(f"    {C.DIM}Enriching {len(enrichable)} backend nodes{C.RST}\n")
    return enrichable


def _load_file_contents(enrichable, root):
    sys.stdout.write(f'    {C.DIM}Reading file contents...{C.RST}')
    sys.stdout.flush()
    fc = {}
    for n in enrichable:
        fp = n['file_path']
        if fp not in fc:
            try: fc[fp] = (root / fp).read_text(errors='ignore').splitlines()
            except Exception: fc[fp] = None
    sys.stdout.write(f"\r\033[K    {C.DIM}{len(fc)} files loaded{C.RST}\n")
    return fc


def _build_batches(enrichable):
    by_file = defaultdict(list)
    for n in enrichable: by_file[n['file_path']].append(n)
    batches, batch, files = [], [], 0
    fpb, npb = cfg.get('llm', 'files_per_batch'), cfg.get('llm', 'nodes_per_batch')
    for fp, nodes in by_file.items():
        batch.extend(nodes); files += 1
        if files >= fpb or len(batch) >= npb:
            batches.append(batch); batch = []; files = 0
    if batch: batches.append(batch)
    return batches


def _compute_and_store_importance(nodes, edges, node_by_id, num_batches):
    sys.stdout.write(f'    {C.DIM}Computing importance scores...{C.RST}')
    sys.stdout.flush()
    from .graph import compute_importance
    importance = compute_importance(nodes, edges)
    sys.stdout.write(f"\r\033[K    {C.DIM}{len(importance)} nodes scored, {num_batches} batches ready{C.RST}\n")
    for nid, score in importance.items():
        if nid in node_by_id:
            sem = node_by_id[nid].get('semantics')
            if sem: sem['importance'] = score
    return importance


def _run_concurrent(batches, file_contents, max_code_chars, edges,
                    node_by_id, importance, llm_url, model, cache_dir):
    enriched, consecutive_errors = 0, 0
    eta = ETATracker(len(batches))
    metrics, lock, stop_flag = [], threading.Lock(), threading.Event()

    def _process_one(idx_batch):
        idx, batch = idx_batch
        pending, combined_result, combined_missing = list(batch), {}, set()
        latency, status, bids = 0.0, 'success', []
        while pending:
            prompt, expected_ids, id_map, included, remaining, tokens = _build_batch_prompt(
                pending, file_contents, max_code_chars, edges, node_by_id, importance)
            if not included: break
            bid = _batch_id(included, tokens); bids.append(bid)
            cached = _get_cached(cache_dir, bid)
            if cached: combined_result.update(cached); pending = remaining; continue
            t0 = time.time()
            raw = _llm_request(llm_url, model, prompt)
            result = _extract_json(raw)
            result = _validate_and_retry(result, expected_ids, llm_url, model, prompt)
            latency += time.time() - t0
            cr = {}
            if result:
                for fid, s in result.items():
                    nid = id_map.get(fid)
                    if nid and isinstance(s, str): cr[nid] = s
                _save_cache(cache_dir, bid, cr)
            combined_result.update(cr)
            missing = set(expected_ids) - set(result.keys()) if result else set(expected_ids)
            if missing: combined_missing.update(missing); status = 'partial'
            pending = remaining
        return idx, ','.join(bids) if bids else _batch_id(batch), combined_result, combined_missing, status, latency

    max_workers = min(cfg.get('llm', 'max_workers'), max(1, len(batches) // 2))
    sys.stdout.write(f'    {C.DIM}Sending to LLM ({max_workers} workers)... waiting for first response{C.RST}')
    sys.stdout.flush()
    first = True
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_process_one, (i, b)): i for i, b in enumerate(batches)}
        for future in as_completed(futures):
            if first: sys.stdout.write("\r\033[K"); first = False
            done = sum(1 for f in futures if f.done())
            try:
                idx, bid, result_map, missing, status, latency = future.result(timeout=600)
                with lock:
                    for nid, s in result_map.items():
                        if nid in node_by_id: node_by_id[nid]['summary'] = s; enriched += 1
                    eta.tick()
                    progress_bar_eta(done, len(batches), eta, f'batch {done}/{len(batches)}')
                    metrics.append({'batch_id': bid, 'status': status, 'size': len(batches[idx]), 'latency': round(latency, 1)})
                    consecutive_errors = 0
            except urllib.error.HTTPError as e:
                with lock:
                    consecutive_errors += 1
                    metrics.append({'batch_id': '', 'status': 'failed', 'error': classify_error(e)})
                    if classify_error(e) == 'auth' or consecutive_errors >= 5: stop_flag.set(); break
            except Exception as e:
                with lock:
                    consecutive_errors += 1
                    metrics.append({'batch_id': '', 'status': 'failed', 'error': str(e)[:100]})
                    if consecutive_errors >= 5: stop_flag.set(); break
    return enriched, metrics


# ─── Multi-Level Enrichment (v0.3) ──────────────────────────────────────────

def enrich_files(nodes: List[dict], edges: List[dict], llm_url: str, model: str = "") -> Dict[str, dict]:
    """Level 2: Aggregate function summaries → file summary with facts."""
    from .graph import get_callees
    file_nodes = {n["id"]: n for n in nodes if n["type"] == "file"}
    func_nodes = {n["id"]: n for n in nodes if n["type"] in ("function", "class")}

    # Map file → contained functions
    file_children = defaultdict(list)
    for e in edges:
        if e["type"] == "contains" and e["source"] in file_nodes and e["target"] in func_nodes:
            file_children[e["source"]].append(func_nodes[e["target"]])

    results = {}
    for fid, children in file_children.items():
        fnode = file_nodes[fid]
        if not any(c.get("summary", "").strip() and not c["summary"].startswith("Function") for c in children):
            continue  # skip files without enriched summaries

        # Aggregate facts from children
        facts = _aggregate_facts(children)
        child_summaries = "\n".join(
            f"- {c['name']}: {c.get('summary', '')[:100]}" for c in children if c.get("summary"))

        prompt = (
            f"Summarize this file based on its functions/classes.\n\n"
            f"File: {fnode['file_path']}\nContains:\n{child_summaries}\n\n"
            f"You MUST preserve these facts:\n"
            f"- external_apis: {facts.get('external_apis', [])}\n"
            f"- db_tables: {facts.get('db_tables', [])}\n"
            f"- domains: {facts.get('domains', [])}\n\n"
            f'Return: {{"summary": "1-2 sentences", "facts": {{"external_apis": [...], "db_tables": [...], "domains": [...]}}}}'
        )
        try:
            raw = _llm_request(llm_url, model, prompt)
            result = _extract_json(raw)
            if result:
                summary = result.get("summary", "")
                rfacts = result.get("facts", facts)
                rfacts = _verify_facts(facts, rfacts)
                results[fid] = {"summary": summary, "facts": rfacts}
                fnode["summary"] = summary
        except Exception:
            pass
    return results


def enrich_modules(modules: Dict[str, List[dict]], file_summaries: Dict[str, dict],
                   llm_url: str, model: str = "") -> Dict[str, dict]:
    """Level 3: Aggregate file summaries → module summary with facts."""
    results = {}
    for mod_name, file_nodes in modules.items():
        file_lines = []
        all_facts = []
        for fn in file_nodes:
            fs = file_summaries.get(fn["id"], {})
            s = fs.get("summary", fn.get("summary", ""))
            if s and not s.startswith("python file") and not s.startswith("javascript file"):
                file_lines.append(f"- {fn['file_path']}: {s[:100]}")
            if fs.get("facts"): all_facts.append(fs["facts"])

        if not file_lines: continue
        merged = merge_facts(all_facts) if all_facts else {}

        prompt = (
            f"Summarize this module.\n\nModule: {mod_name}/\nFiles:\n" + "\n".join(file_lines) +
            f"\n\nPreserve facts: {json.dumps(merged)}\n"
            f'Return: {{"summary": "1-2 sentences", "facts": {{...}}}}'
        )
        try:
            raw = _llm_request(llm_url, model, prompt)
            result = _extract_json(raw)
            if result:
                results[mod_name] = {"summary": result.get("summary", ""), "facts": result.get("facts", merged)}
        except Exception:
            pass
    return results


# ─── Fact Helpers ────────────────────────────────────────────────────────────

def _aggregate_facts(children: List[dict]) -> dict:
    """Extract facts from semantic fields of child nodes."""
    facts = {"external_apis": set(), "db_tables": set(), "domains": set(), "side_effects": set()}
    for c in children:
        sem = c.get("semantics", {})
        for eff in sem.get("side_effects", []):
            t = eff["type"] if isinstance(eff, dict) else eff
            if ":" in t:
                prefix, entity = t.split(":", 1)
                if "api" in prefix: facts["external_apis"].add(entity)
                elif "db" in prefix: facts["db_tables"].add(entity)
                facts["side_effects"].add(prefix)
            else:
                facts["side_effects"].add(t)
        if sem.get("domain_hint"): facts["domains"].add(sem["domain_hint"])
    return {k: sorted(v) for k, v in facts.items() if v}


def merge_facts(facts_list: List[dict]) -> dict:
    """Merge multiple fact dicts, deduplicating."""
    merged = defaultdict(set)
    for facts in facts_list:
        for key, values in facts.items():
            if isinstance(values, list):
                merged[key].update(values)
            elif isinstance(values, str):
                merged[key].add(values)
    return {k: sorted(v) for k, v in merged.items() if v}


def _verify_facts(original: dict, summary_facts: dict) -> dict:
    """Ensure LLM didn't drop critical facts."""
    for key in original:
        orig = set(original[key]) if isinstance(original[key], list) else {original[key]}
        summ = set(summary_facts.get(key, []))
        lost = orig - summ
        if lost:
            summary_facts.setdefault(key, [])
            if isinstance(summary_facts[key], list):
                summary_facts[key].extend(sorted(lost))
            else:
                summary_facts[key] = sorted(orig | summ)
    return summary_facts


def detect_modules(nodes: List[dict]) -> Dict[str, List[dict]]:
    """Group file nodes by top-level directory."""
    modules = defaultdict(list)
    for n in nodes:
        if n["type"] != "file": continue
        parts = n.get("file_path", "").split("/")
        module = parts[0] if len(parts) > 1 else "root"
        modules[module].append(n)
    return dict(modules)
