"""
Complexity analysis engine.

To add a new framework/language rule:
  1. Create a file in src/complexity/rules/  (e.g. my_framework.py)
  2. Define BRANCH_PATTERNS, FRAMEWORK_PATTERNS, FRAMEWORK_HINTS dicts
  3. It will be auto-discovered at import time
"""

import re, math
from typing import Dict, List

# ─── Registry (populated by rule modules) ───────────────────────────────────

BRANCH_PATTERNS: Dict[str, str] = {}
FRAMEWORK_PATTERNS: Dict[str, list] = {}
FRAMEWORK_HINTS: Dict[str, str] = {}

_compiled_branches: Dict[str, re.Pattern] = {}

COGNITIVE_WEIGHTS = {
    "nesting":   1.5,
    "recursion": 2.0,
    "callback":  1.5,
    "ternary":   0.5,
}


def register_rules(*, branches: dict = None, frameworks: dict = None, hints: dict = None):
    """Called by rule modules to register their patterns."""
    if branches:   BRANCH_PATTERNS.update(branches)
    if frameworks: FRAMEWORK_PATTERNS.update(frameworks)
    if hints:      FRAMEWORK_HINTS.update(hints)


# ─── Auto-discover rule modules ─────────────────────────────────────────────

def _load_rules():
    import importlib, pkgutil
    from . import rules as rules_pkg
    for _, name, _ in pkgutil.iter_modules(rules_pkg.__path__):
        importlib.import_module(f".rules.{name}", package=__package__)

_load_rules()


# ─── Internal helpers ────────────────────────────────────────────────────────

def _get_branch_pattern(lang: str) -> re.Pattern:
    if lang in _compiled_branches:
        return _compiled_branches[lang]
    raw = BRANCH_PATTERNS.get(lang, BRANCH_PATTERNS.get("python", r'^\s*(?:if |for |while )'))
    pat = re.compile(raw, re.MULTILINE)
    _compiled_branches[lang] = pat
    return pat


def _detect_frameworks(source: str) -> List[str]:
    detected = []
    for fw, pat in FRAMEWORK_HINTS.items():
        if re.search(pat, source, re.IGNORECASE):
            detected.append(fw)
    return detected


def _count_nesting(source: str, lang: str) -> int:
    if lang in ("python", "ruby", "lua", "shell"):
        indent = 4 if lang == "python" else 2
        depths = [len(m.group(1)) // indent for m in re.finditer(r'^( +)\S', source, re.MULTILINE)]
        return max(depths, default=0)
    depth = max_depth = 0
    for ch in source:
        if ch == '{': depth += 1; max_depth = max(max_depth, depth)
        elif ch == '}': depth = max(0, depth - 1)
    return max_depth


def _count_params(source: str, lang: str) -> int:
    if lang == "python":
        sigs = re.findall(r'def \w+\(([^)]*)\)', source)
    elif lang in ("java", "kotlin", "csharp", "swift", "go", "rust", "c", "cpp", "scala"):
        sigs = re.findall(r'(?:func|fun|fn|def|void|int|string|bool|var)\s+\w+\s*\(([^)]*)\)', source, re.IGNORECASE)
    else:
        sigs = re.findall(r'function\s*\w*\s*\(([^)]*)\)', source)
    if not sigs:
        return 0
    return max(len([p for p in sig.split(',') if p.strip()]) for sig in sigs)


# ─── Public API ──────────────────────────────────────────────────────────────

def estimate_complexity(line_count: int, source: str = "", lang: str = "") -> str:
    if not source:
        if line_count <= 30: return "simple"
        if line_count <= 150: return "moderate"
        return "complex"

    lang = lang or "python"

    branches = len(_get_branch_pattern(lang).findall(source))
    nesting = _count_nesting(source, lang)
    nesting_score = nesting ** 1.5

    size_score = math.log2(max(line_count, 1)) * 0.8

    cognitive = 0.0
    func_names = re.findall(r'(?:def|function|func|fn)\s+(\w+)', source)
    for name in func_names:
        if re.search(r'\b' + re.escape(name) + r'\s*\(', source.split(name, 1)[-1] if name in source else ""):
            cognitive += COGNITIVE_WEIGHTS["recursion"]; break

    if lang in ("javascript", "typescript"):
        callbacks = len(re.findall(r'(?:=>|function\s*\()', source))
        if callbacks > 2:
            cognitive += (callbacks - 2) * COGNITIVE_WEIGHTS["callback"]

    ternaries = len(re.findall(r'\?[^?].*:', source))
    cognitive += ternaries * COGNITIVE_WEIGHTS["ternary"]

    fw_score = 0.0
    for fw in _detect_frameworks(source):
        for pat, weight in FRAMEWORK_PATTERNS.get(fw, []):
            fw_score += len(re.findall(pat, source)) * weight

    max_params = _count_params(source, lang)
    param_score = max(0, max_params - 3) * 0.8

    score = branches + nesting_score + size_score + cognitive + fw_score + param_score

    if score <= 8:  return "simple"
    if score <= 22: return "moderate"
    return "complex"
