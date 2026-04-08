"""LLM enrichment — structured batch, validation, context-aware prompts."""

import sys, json, re, time, hashlib, urllib.request, urllib.error
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
from .ui import C, progress_bar_eta, ETATracker

DEFAULT_LLM_URL = "http://localhost:1234/v1/chat/completions"

# ─── HTTP ────────────────────────────────────────────────────────────────────

def _llm_request(url: str, model: str, prompt: str,
                 timeout: int = 300, max_retries: int = 3) -> str:
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

def _batch_id(items: list) -> str:
    content = json.dumps([(n["id"], n["name"]) for n in items], sort_keys=True)
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

TOP_K_CALLERS = 2
TOP_K_CALLEES = 3

def _select_context(node: dict, edges: List[dict], node_by_id: Dict[str, dict],
                    importance: Dict[str, float]) -> str:
    """Build context string for a node: callers + callees sorted by importance."""
    nid = node["id"]
    callers = [e["source"] for e in edges if e["target"] == nid and e["type"] == "calls"]
    callees = [e["target"] for e in edges if e["source"] == nid and e["type"] == "calls"]

    callers = sorted(callers, key=lambda x: importance.get(x, 0), reverse=True)[:TOP_K_CALLERS]
    callees = sorted(callees, key=lambda x: importance.get(x, 0), reverse=True)[:TOP_K_CALLEES]

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
                        importance: Dict[str, float] = None) -> Tuple[str, List[str], Dict[str, str]]:
    """Build structured prompt for a batch. Returns (prompt, expected_ids, id_to_node_id)."""
    blocks = []
    expected_ids = []
    id_map = {}  # fN → node["id"]
    total_chars = 0

    for i, n in enumerate(batch_nodes):
        lines = file_contents.get(n["file_path"])
        if lines is None: continue
        s, e = max(0, n["line_range"][0] - 2), min(len(lines), n["line_range"][1] + 1)
        snippet = "\n".join(lines[s:e])
        if len(snippet) > 3000: snippet = snippet[:3000] + "\n..."
        if total_chars + len(snippet) > max_code_chars and blocks: break
        total_chars += len(snippet)

        fid = f"f{i}"
        block = _build_func_block(n, snippet, i)
        # Inject context if available
        if edges and node_by_id and importance:
            ctx = _select_context(n, edges, node_by_id, importance)
            if ctx: block = block.replace("</FUNC>", f"{ctx}\n</FUNC>")
        blocks.append(block)
        expected_ids.append(fid)
        id_map[fid] = n["id"]

    prompt = (
        "Analyze these functions. Each has an ID. Return a JSON object keyed by ID with 1-2 sentence summaries.\n\n"
        + "\n\n".join(blocks)
        + f'\n\nReturn ONLY: {{"f0": "summary...", "f1": "summary...", ...}}'
    )
    return prompt, expected_ids, id_map

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

def enrich_with_llm(nodes: List[dict], edges: List[dict], root: Path,
                    llm_url: str, model: str = "",
                    context_size: int = 8192, max_enrich: int = 0,
                    output_dir: Path = None) -> int:
    max_code_chars = min((context_size - 800) * 3, 15000)
    cache_dir = (output_dir / "cache") if output_dir else None

    enrichable = [n for n in nodes if n["type"] in ("function", "class")
                  and n.get("file_path") and n.get("language", "") in ENRICH_LANGS
                  and not (SKIP_PATHS & set(n["file_path"].lower().split("/")))]
    if not enrichable: return 0

    skipped_fe = sum(1 for n in nodes if n["type"] in ("function", "class")
                     and n.get("language", "") in {"css","html","markdown","json","yaml","toml","xml","dockerfile","terraform","makefile"})
    skipped_test = sum(1 for n in nodes if n["type"] in ("function", "class")
                       and n.get("file_path") and (SKIP_PATHS & set(n["file_path"].lower().split("/"))))
    if skipped_fe or skipped_test:
        sys.stdout.write(f"\n    {C.DIM}Skipping {skipped_fe} config/frontend + {skipped_test} test nodes{C.RST}\n")

    # Sort by complexity (complex first)
    comp_score = {"complex": 3, "moderate": 2, "simple": 1}
    type_score = {"class": 2, "function": 1}
    enrichable.sort(key=lambda n: (comp_score.get(n.get("complexity"), 0), type_score.get(n["type"], 0)), reverse=True)

    if max_enrich > 0: enrichable = enrichable[:max_enrich]
    sys.stdout.write(f"    {C.DIM}Enriching {len(enrichable)} backend nodes{C.RST}\n")

    # Read file contents once
    file_contents: Dict[str, list] = {}
    for n in enrichable:
        fp = n["file_path"]
        if fp not in file_contents:
            try: file_contents[fp] = (root / fp).read_text(errors="ignore").splitlines()
            except Exception: file_contents[fp] = None

    # Batch by file (10-20 files per batch)
    by_file = defaultdict(list)
    for n in enrichable: by_file[n["file_path"]].append(n)

    batches: List[List[dict]] = []
    current_batch = []
    current_files = 0
    for fp, file_nodes in by_file.items():
        current_batch.extend(file_nodes)
        current_files += 1
        if current_files >= 15 or len(current_batch) >= 30:
            batches.append(current_batch)
            current_batch = []
            current_files = 0
    if current_batch: batches.append(current_batch)

    # Node lookup for applying results
    node_by_id = {n["id"]: n for n in nodes}

    # Compute importance for context selection
    from .graph import compute_importance
    importance = compute_importance(nodes, edges)
    for nid, score in importance.items():
        if nid in node_by_id:
            sem = node_by_id[nid].get("semantics")
            if sem: sem["importance"] = score

    # Process batches
    enriched = 0
    consecutive_errors = 0
    eta = ETATracker(len(batches))
    metrics = []  # for observability

    for idx, batch in enumerate(batches, 1):
        progress_bar_eta(idx, len(batches), eta, f"batch {idx}/{len(batches)}")
        bid = _batch_id(batch)

        # Check cache
        cached = _get_cached(cache_dir, bid)
        if cached:
            for node_id, summary in cached.items():
                if node_id in node_by_id: node_by_id[node_id]["summary"] = summary; enriched += 1
            eta.tick()
            metrics.append({"batch_id": bid, "status": "cached", "size": len(batch)})
            continue

        t0 = time.time()
        prompt, expected_ids, id_map = _build_batch_prompt(batch, file_contents, max_code_chars,
                                                            edges, node_by_id, importance)

        try:
            raw = _llm_request(llm_url, model, prompt)
            result = _extract_json(raw)
            result = _validate_and_retry(result, expected_ids, llm_url, model, prompt)
            latency = time.time() - t0
            eta.tick()

            if result:
                cache_result = {}
                for fid, summary in result.items():
                    node_id = id_map.get(fid)
                    if node_id and node_id in node_by_id and isinstance(summary, str):
                        node_by_id[node_id]["summary"] = summary
                        cache_result[node_id] = summary
                        enriched += 1
                _save_cache(cache_dir, bid, cache_result)

            missing = set(expected_ids) - set(result.keys()) if result else set(expected_ids)
            metrics.append({"batch_id": bid, "status": "success" if not missing else "partial",
                           "size": len(batch), "latency": round(latency, 1),
                           "missing_ids": list(missing), "tokens_est": len(prompt) // 4})
            consecutive_errors = 0

        except urllib.error.HTTPError as e:
            body = ""
            try: body = e.read().decode(errors="ignore")[:300]
            except Exception: pass
            err_type = classify_error(e)
            if err_type == "auth":
                sys.stdout.write(f"\n   ✗ Auth failed ({e.code}). {body}\n"); break
            consecutive_errors += 1
            metrics.append({"batch_id": bid, "status": "failed", "error": err_type, "size": len(batch)})
            sys.stdout.write(f"\n   ⚠ Batch {idx} failed ({e.code}): {body[:150]}\n")
            if consecutive_errors >= 5:
                sys.stdout.write(f"   ✗ Too many errors, stopping.\n"); break

        except Exception as e:
            err_type = classify_error(e)
            consecutive_errors += 1
            metrics.append({"batch_id": bid, "status": "failed", "error": err_type, "size": len(batch)})
            sys.stdout.write(f"\n   ⚠ Batch {idx}: {e}\n")
            if consecutive_errors >= 5: break

    del file_contents

    # Save metrics
    if output_dir and metrics:
        try:
            (output_dir / "metrics.json").write_text(json.dumps({
                "total_batches": len(batches), "enriched": enriched,
                "batches": metrics}, indent=2))
        except Exception: pass

    return enriched
