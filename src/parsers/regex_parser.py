"""Regex-based parsers for non-Python languages."""

import re
from typing import List
from ..types import ParseResult

RE_PATTERNS = {
    "javascript": {
        "function": [r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)",
            r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>",
            r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function"],
        "class": [r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?"],
        "import": [r"import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+['\"]([^'\"]+)['\"]",
            r"import\s+['\"]([^'\"]+)['\"]",
            r"(?:const|let|var)\s+(?:\{([^}]+)\}|(\w+))\s*=\s*require\(['\"]([^'\"]+)['\"]\)"],
        "export": [r"export\s+(?:default\s+)?(?:class|function|const|let|var|async)\s+(\w+)", r"export\s+\{([^}]+)\}"],
    },
    "java": {
        "function": [r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w,\s]+)?\s*\{"],
        "class": [r"(?:public\s+)?(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?"],
        "import": [r"import\s+(?:static\s+)?([\w.]+)(?:\.\*)?;"], "export": [],
    },
    "go": {
        "function": [r"func\s+(?:\(\w+\s+\*?(\w+)\)\s+)?(\w+)\s*\(([^)]*)\)"],
        "class": [r"type\s+(\w+)\s+struct\s*\{", r"type\s+(\w+)\s+interface\s*\{"],
        "import": [r"\"([\w./\-]+)\""], "export": [],
    },
    "rust": {
        "function": [r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"],
        "class": [r"(?:pub\s+)?struct\s+(\w+)", r"(?:pub\s+)?enum\s+(\w+)", r"(?:pub\s+)?trait\s+(\w+)"],
        "import": [r"use\s+([\w:]+)(?:::\{([^}]+)\})?;"], "export": [],
    },
    "ruby": {
        "function": [r"def\s+(?:self\.)?(\w+)(?:\(([^)]*)\))?"],
        "class": [r"class\s+(\w+)(?:\s*<\s*(\w+))?", r"module\s+(\w+)"],
        "import": [r"require\s+['\"]([^'\"]+)['\"]", r"require_relative\s+['\"]([^'\"]+)['\"]"], "export": [],
    },
    "php": {
        "function": [r"(?:public|private|protected|static|\s)*function\s+(\w+)\s*\(([^)]*)\)"],
        "class": [r"(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?"],
        "import": [r"use\s+([\w\\]+)(?:\s+as\s+(\w+))?;", r"(?:require|include)(?:_once)?\s+['\"]([^'\"]+)['\"]"], "export": [],
    },
    "csharp": {
        "function": [r"(?:public|private|protected|internal|static|async|virtual|override|\s)+[\w<>\[\]?]+\s+(\w+)\s*\(([^)]*)\)\s*\{"],
        "class": [r"(?:public\s+)?(?:abstract\s+)?(?:partial\s+)?(?:class|interface|struct|enum|record)\s+(\w+)(?:\s*:\s*([\w,\s<>]+))?"],
        "import": [r"using\s+(?:static\s+)?([\w.]+);"], "export": [],
    },
    "kotlin": {
        "function": [r"(?:fun|suspend\s+fun)\s+(?:<[^>]*>\s+)?(\w+)\s*\(([^)]*)\)"],
        "class": [r"(?:data\s+|sealed\s+|abstract\s+|open\s+)?class\s+(\w+)", r"(?:fun\s+)?interface\s+(\w+)", r"object\s+(\w+)"],
        "import": [r"import\s+([\w.]+)"], "export": [],
    },
    "swift": {
        "function": [r"func\s+(\w+)\s*\(([^)]*)\)"],
        "class": [r"(?:class|struct|protocol|enum)\s+(\w+)(?:\s*:\s*([\w,\s]+))?"],
        "import": [r"import\s+(\w+)"], "export": [],
    },
}
RE_PATTERNS["typescript"] = RE_PATTERNS["javascript"]


def _find_block_end(lines: List[str], start: int, lang: str) -> int:
    if lang in ("python", "ruby"):
        indent = len(lines[start]) - len(lines[start].lstrip()) if start < len(lines) else 0
        for i in range(start + 1, min(start + 500, len(lines))):
            stripped = lines[i].strip()
            if stripped and (len(lines[i]) - len(lines[i].lstrip())) <= indent:
                return i
        return min(start + 10, len(lines))
    depth, found_open = 0, False
    for i in range(start, min(start + 500, len(lines))):
        for ch in lines[i]:
            if ch == "{": depth += 1; found_open = True
            elif ch == "}":
                depth -= 1
                if found_open and depth == 0: return i + 1
    return min(start + 10, len(lines))


def parse_with_regex(content: str, lang: str) -> ParseResult:
    r = ParseResult()
    patterns = RE_PATTERNS.get(lang)
    if not patterns: return r
    lines = content.split("\n")
    for pat in patterns.get("function", []):
        for m in re.finditer(pat, content, re.MULTILINE):
            name = m.group(2) if lang == "go" and m.lastindex and m.lastindex >= 2 else m.group(1)
            if not name or name in ("if","for","while","switch","catch","return"): continue
            line = content[:m.start()].count("\n") + 1
            params_str = m.group(m.lastindex) if m.lastindex and m.lastindex > 1 else ""
            params = [p.strip().split()[-1].split(":")[-1] for p in (params_str or "").split(",") if p.strip()] if params_str else []
            r.functions.append({"name": name, "line_start": line, "line_end": _find_block_end(lines, line-1, lang), "params": params, "decorators": []})
    for pat in patterns.get("class", []):
        for m in re.finditer(pat, content, re.MULTILINE):
            line = content[:m.start()].count("\n") + 1
            bases = [b.strip() for b in m.group(2).split(",") if b.strip()] if m.lastindex and m.lastindex >= 2 and m.group(2) else []
            r.classes.append({"name": m.group(1), "line_start": line, "line_end": _find_block_end(lines, line-1, lang), "methods": [], "bases": bases, "decorators": []})
    for pat in patterns.get("import", []):
        for m in re.finditer(pat, content, re.MULTILINE):
            groups = [g for g in m.groups() if g]
            source = groups[-1] if groups else ""
            specs = [s.strip() for s in groups[0].split(",") if s.strip()] if len(groups) > 1 else []
            r.imports.append({"source": source, "specifiers": specs, "line": content[:m.start()].count("\n") + 1})
    for pat in patterns.get("export", []):
        for m in re.finditer(pat, content, re.MULTILINE):
            for n in m.group(1).split(","):
                n = n.strip().split(" as ")[0].strip()
                if n: r.exports.append({"name": n, "line": content[:m.start()].count("\n") + 1})
    return r
