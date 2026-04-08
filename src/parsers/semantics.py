"""Semantic extraction — side effects, domain, role, control flow."""

import re
from typing import List
from ..types import SideEffect, SemanticInfo

# ─── Patterns ────────────────────────────────────────────────────────────────

SIDE_EFFECT_PATTERNS = {
    "db_write":     re.compile(r"\.save\(|\.create\(|\.update\(|\.delete\(|\.destroy\(|\.insert\(|\.upsert\(|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\.execute\(", re.I),
    "db_read":      re.compile(r"\.find\(|\.findOne\(|\.get\(|\.query\(|\.fetch\(|\.where\(|\.select\(|\bSELECT\b|\.all\(|\.first\(|\.count\(", re.I),
    "external_api": re.compile(r"\bfetch\(|axios\.|requests\.\w+\(|http\.\w+\(|urllib\.|curl_|Guzzle|HttpClient|\.post\(|\.put\(|\.patch\(", re.I),
    "file_io":      re.compile(r"\bopen\(|readFile|writeFile|\bfs\.|fopen|file_put|file_get|Path\(.*\)\.(?:read|write)", re.I),
    "state_mutate": re.compile(r"setState|\.commit\(|\.dispatch\(|this\.\w+\s*=|self\.\w+\s*=", re.I),
}

DOMAIN_KEYWORDS = {
    "payment": ["payment","charge","invoice","stripe","billing","price","cart","refund","checkout","order"],
    "auth":    ["auth","login","logout","token","session","password","jwt","oauth","credential","permission"],
    "user":    ["user","profile","account","register","signup","member"],
    "email":   ["email","mail","smtp","notification","subscribe"],
    "storage": ["upload","download","s3","bucket","blob","attachment"],
    "search":  ["search","filter","elastic","solr","algolia"],
    "admin":   ["admin","dashboard","manage","role","backoffice"],
}

ROLE_PATTERNS = {
    "entry_point":  re.compile(r"Controller|Handler|Route|Endpoint|Command|CLI|Servlet|Resource|View", re.I),
    "orchestrator": re.compile(r"Service|Manager|Processor|UseCase|Interactor|Facade|Coordinator", re.I),
    "validator":    re.compile(r"Validator|Guard|Middleware|Filter|Policy|Sanitizer", re.I),
    "data_access":  re.compile(r"Repository|Repo|DAO|Model|Store|Gateway|Mapper|Entity", re.I),
    "adapter":      re.compile(r"Adapter|Client|Provider|Connector|Driver|Wrapper", re.I),
}

CONTROL_FLOW_PATTERNS = {
    "branching": re.compile(r"\bif\b|\bswitch\b|\bcase\b|\bmatch\b"),
    "loop":      re.compile(r"\bfor\b|\bwhile\b|\bforeach\b|\.map\(|\.forEach\(|\.each\b"),
    "try_catch": re.compile(r"\btry\b.*\bcatch\b|\btry\b.*\bexcept\b|\bfinally\b", re.S),
    "async":     re.compile(r"\basync\b|\bawait\b|\.then\(|\bPromise\b|\bFuture\b|\bTask\b"),
}

ENTITY_ALIASES = {
    "stripegateway": "stripe", "stripeclient": "stripe", "stripe_service": "stripe",
    "txn": "transactions", "transaction": "transactions",
    "usr": "users", "user_model": "users",
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def normalize_entity(name: str) -> str:
    key = name.lower().replace("-", "_").replace(" ", "_")
    return ENTITY_ALIASES.get(key, key)


def _extract_entity(effect_type: str, content: str, imports: List[str]) -> str:
    """Refine side effect type with entity. e.g. external_api → external_api:stripe"""
    if effect_type == "external_api":
        for imp in imports:
            il = imp.lower()
            for svc in ("stripe","twilio","sendgrid","paypal","aws","redis","rabbitmq","kafka"):
                if svc in il:
                    return f"external_api:{svc}"
    if effect_type in ("db_write", "db_read"):
        m = re.search(r"(\w+)::\w+\(|(\w+)->(?:save|create|update|delete|find|where)", content)
        if m:
            entity = normalize_entity((m.group(1) or m.group(2)))
            return f"{effect_type}:{entity}"
    return effect_type


def _detect_domain(name: str, content: str, file_path: str) -> str:
    text = f"{name} {file_path}".lower()
    best, best_score = "", 0
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        # Also check content but with lower weight
        score += sum(0.3 for kw in keywords if kw in content[:2000].lower())
        if score > best_score:
            best, best_score = domain, score
    return best if best_score >= 1.0 else ""


def _detect_role(name: str, file_path: str) -> str:
    text = f"{name} {file_path}"
    for role, pat in ROLE_PATTERNS.items():
        if pat.search(text):
            return role
    return ""


# ─── Public API ──────────────────────────────────────────────────────────────

def extract_semantics(content: str, name: str, file_path: str,
                      imports: List[str] = None, lang: str = "") -> SemanticInfo:
    """Extract semantic info from code content."""
    imports = imports or []
    sem = SemanticInfo()

    # Side effects
    for effect_type, pat in SIDE_EFFECT_PATTERNS.items():
        if pat.search(content):
            refined = _extract_entity(effect_type, content, imports)
            conf = 0.9 if "::" in refined or "->" in content else 0.7
            sem.side_effects.append(SideEffect(type=refined, confidence=conf, source="regex"))

    # Import-inferred side effects
    for imp in imports:
        il = imp.lower()
        for svc in ("stripe","twilio","sendgrid","paypal","redis","rabbitmq","kafka","elasticsearch"):
            if svc in il and not any(svc in se.type for se in sem.side_effects):
                sem.side_effects.append(SideEffect(type=f"external_api:{svc}", confidence=0.6, source="import_inference"))

    # Control flow
    for flow_type, pat in CONTROL_FLOW_PATTERNS.items():
        if pat.search(content):
            sem.control_flow.append(flow_type)

    # Domain
    sem.domain_hint = _detect_domain(name, content, file_path)

    # Role
    sem.execution_role = _detect_role(name, file_path)

    return sem
