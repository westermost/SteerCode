import sys, json, re, urllib.request, urllib.error
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
from .ui import C, progress_bar

DEFAULT_LLM_URL = "http://localhost:1234/v1/chat/completions"

def _llm_request(url: str, model: str, prompt: str) -> str:
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/")
        if url.endswith("/v1/completions"):
            url = url.replace("/v1/completions", "/v1/chat/completions")
        elif not url.endswith("/v1/chat/completions"):
            url = url + "/v1/chat/completions"
    payload = {"max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]}
    if model: payload["model"] = model
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]

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

def enrich_with_llm(nodes: List[dict], edges: List[dict], root: Path,
                     llm_url: str, model: str = "",
                     context_size: int = 8192, max_enrich: int = 0) -> int:
    max_code_chars = min((context_size - 800) * 3, 15000)

    ENRICH_LANGS = {"python","javascript","typescript","java","go","rust","c","cpp",
                    "csharp","ruby","php","swift","kotlin","scala","lua","shell","sql"}

    enrichable = [n for n in nodes if n["type"] in ("function","class")
                  and n.get("file_path") and n.get("language","") in ENRICH_LANGS]
    if not enrichable: return 0

    skipped_fe = sum(1 for n in nodes if n["type"] in ("function","class")
                     and n.get("language","") in {"css","html","markdown","json","yaml","toml","xml","dockerfile","terraform"})
    if skipped_fe:
        sys.stdout.write(f"\n    {C.DIM}Skipping {skipped_fe} frontend/config nodes{C.RST}\n")

    comp_score = {"complex":3, "moderate":2, "simple":1}
    type_score = {"class":2, "function":1}
    enrichable.sort(key=lambda n: (comp_score.get(n.get("complexity"),0), type_score.get(n["type"],0)), reverse=True)

    if max_enrich > 0 and len(enrichable) > max_enrich:
        enrichable = enrichable[:max_enrich]
        sys.stdout.write(f"    {C.DIM}Enriching top {max_enrich} BE nodes{C.RST}\n")
    else:
        sys.stdout.write(f"    {C.DIM}Enriching {len(enrichable)} backend nodes{C.RST}\n")

    # Group by file, build batches
    file_groups: Dict[str, List[dict]] = defaultdict(list)
    for n in enrichable: file_groups[n["file_path"]].append(n)

    batches: List[List[Tuple[str, dict, str]]] = []
    current_batch, current_chars = [], 0

    for fpath, file_nodes in file_groups.items():
        try: lines = (root / fpath).read_text(errors="ignore").splitlines()
        except Exception: continue
        for n in file_nodes:
            s, e = max(0, n["line_range"][0]-2), min(len(lines), n["line_range"][1]+1)
            snippet = "\n".join(lines[s:e])
            if len(snippet) > max_code_chars: snippet = snippet[:max_code_chars] + "\n..."
            cost = len(snippet) + 100
            if current_chars + cost > max_code_chars and current_batch:
                batches.append(current_batch); current_batch = []; current_chars = 0
            current_batch.append((fpath, n, snippet)); current_chars += cost
    if current_batch: batches.append(current_batch)

    enriched, consecutive_errors = 0, 0
    for idx, batch in enumerate(batches, 1):
        progress_bar(idx, len(batches), f"Enriching batch {idx}/{len(batches)}")
        snippets = "".join(f"\n### {n['type']} `{n['name']}` in {fp}\n```\n{s}\n```\n" for fp,n,s in batch)
        prompt = f'Analyze these code snippets and provide concise summaries.\n{snippets}\nReturn ONLY a JSON object mapping each name to a 1-2 sentence summary.'

        try:
            result = _extract_json(_llm_request(llm_url, model, prompt))
            if result:
                result_lower = {k.lower(): v for k, v in result.items()}
                for _, n, _ in batch:
                    for c in [n["name"], f"{n['type']}_{n['name']}", f"{n['type']}{n['name']}"]:
                        if c in result: n["summary"] = result[c]; enriched += 1; break
                        elif c.lower() in result_lower: n["summary"] = result_lower[c.lower()]; enriched += 1; break
            consecutive_errors = 0
        except urllib.error.HTTPError as e:
            body = ""
            try: body = e.read().decode(errors="ignore")[:300]
            except Exception: pass
            if e.code in (401,403): sys.stdout.write(f"\n   ✗ Auth failed ({e.code}). {body}\n"); break
            consecutive_errors += 1
            batch_chars = sum(len(s) for _,_,s in batch)
            sys.stdout.write(f"\n   ⚠ Batch {idx} failed ({e.code}): {body[:150]}\n")
            sys.stdout.write(f"     {C.DIM}~{batch_chars} chars{C.RST}\n")
            if consecutive_errors >= 5: sys.stdout.write(f"   ✗ Too many errors, skipping.\n"); break
        except Exception as e:
            consecutive_errors += 1
            sys.stdout.write(f"\n   ⚠ Batch {idx}: {e}\n")
            if consecutive_errors >= 5: break
    return enriched
