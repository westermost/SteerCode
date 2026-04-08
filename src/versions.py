"""Detect language/framework versions and dependencies from project config files."""

import json, re
from pathlib import Path
from typing import Dict, List, Optional


def detect_versions(root: Path, llm_fn=None) -> Dict:
    """Scan root for version/dependency files. If llm_fn provided, use LLM for ambiguous cases."""
    result = {"runtime": {}, "frameworks": {}, "packages": {}}

    # Search root and one level deep (monorepo support)
    roots = [root] + [d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".") and d.name not in {"vendor", "node_modules", ".git"}]

    for r in roots:
        _detect_php(r, result)
        _detect_node(r, result)
        _detect_python(r, result)
        _detect_go(r, result)
        _detect_ruby(r, result)
        _detect_docker(r, result)

    if llm_fn:
        _enrich_versions_llm(root, result, llm_fn)

    return {k: v for k, v in result.items() if v}


def _read_json(path: Path) -> Optional[dict]:
    try: return json.loads(path.read_text(errors="ignore"))
    except Exception: return None


def _detect_php(root: Path, result: Dict):
    # composer.json
    cj = _read_json(root / "composer.json")
    if not cj: return
    req = cj.get("require", {})
    req_dev = cj.get("require-dev", {})

    if "php" in req:
        result["runtime"]["php"] = req["php"]

    # Detect PHP version from Dockerfile if not in composer
    if "php" not in result["runtime"]:
        for df in ["Dockerfile", "develop.dockerfile"]:
            p = root / df
            if p.exists():
                content = p.read_text(errors="ignore")
                m = re.search(r'php(\d+)[\.\-]', content, re.IGNORECASE)
                if m:
                    ver = m.group(1)
                    result["runtime"]["php"] = f"{ver[0]}.{ver[1:]}" if len(ver) > 1 else ver
                    break

    # Frameworks
    fw_map = {
        "symfony/symfony": "Symfony", "symfony/framework-bundle": "Symfony",
        "laravel/framework": "Laravel", "cakephp/cakephp": "CakePHP",
        "slim/slim": "Slim", "yiisoft/yii2": "Yii2",
    }
    for pkg, fw in fw_map.items():
        if pkg in req:
            result["frameworks"][fw] = req[pkg]

    # Key packages
    pkgs = {}
    for name, ver in {**req, **req_dev}.items():
        if name != "php" and not name.startswith("ext-"):
            pkgs[name] = ver
    if pkgs:
        result["packages"]["composer"] = {"count": len(pkgs), "key": dict(list(pkgs.items())[:15])}


def _detect_node(root: Path, result: Dict):
    # .node-version / .nvmrc
    for f in [".node-version", ".nvmrc"]:
        p = root / f
        if p.exists():
            result["runtime"]["node"] = p.read_text(errors="ignore").strip()
            break

    pj = _read_json(root / "package.json")
    if not pj: return

    engines = pj.get("engines", {})
    if "node" in engines and "node" not in result["runtime"]:
        result["runtime"]["node"] = engines["node"]
    if "npm" in engines:
        result["runtime"]["npm"] = engines["npm"]

    # Frameworks
    all_deps = {**pj.get("dependencies", {}), **pj.get("devDependencies", {})}
    fw_map = {
        "react": "React", "next": "Next.js", "vue": "Vue", "nuxt": "Nuxt",
        "@angular/core": "Angular", "svelte": "Svelte", "express": "Express",
        "gatsby": "Gatsby", "remix": "Remix",
    }
    for pkg, fw in fw_map.items():
        if pkg in all_deps:
            result["frameworks"][fw] = all_deps[pkg]

    deps = pj.get("dependencies", {})
    dev = pj.get("devDependencies", {})
    if deps or dev:
        result["packages"]["npm"] = {"count": len(deps) + len(dev), "key": dict(list(deps.items())[:10])}


def _detect_python(root: Path, result: Dict):
    # pyproject.toml
    pp = root / "pyproject.toml"
    if pp.exists():
        content = pp.read_text(errors="ignore")
        m = re.search(r'requires-python\s*=\s*["\']([^"\']+)', content)
        if m: result["runtime"]["python"] = m.group(1)

    # requirements.txt
    req = root / "requirements.txt"
    if req.exists():
        lines = [l.strip() for l in req.read_text(errors="ignore").splitlines() if l.strip() and not l.startswith("#")]
        pkgs = {}
        for l in lines[:15]:
            parts = re.split(r'[=<>!~]', l, 1)
            pkgs[parts[0].strip()] = l[len(parts[0]):].strip("=<>!~ ") if len(parts) > 1 else "*"
        if pkgs:
            result["packages"]["pip"] = {"count": len(lines), "key": pkgs}


def _detect_go(root: Path, result: Dict):
    gomod = root / "go.mod"
    if not gomod.exists(): return
    content = gomod.read_text(errors="ignore")
    m = re.search(r'^go\s+([\d.]+)', content, re.MULTILINE)
    if m: result["runtime"]["go"] = m.group(1)
    reqs = re.findall(r'^\t([\w./\-]+)\s+(v[\d.]+)', content, re.MULTILINE)
    if reqs:
        result["packages"]["go"] = {"count": len(reqs), "key": dict(reqs[:10])}


def _detect_ruby(root: Path, result: Dict):
    rv = root / ".ruby-version"
    if rv.exists():
        result["runtime"]["ruby"] = rv.read_text(errors="ignore").strip()
    gf = root / "Gemfile"
    if gf.exists():
        content = gf.read_text(errors="ignore")
        m = re.search(r"ruby\s+['\"]([^'\"]+)", content)
        if m and "ruby" not in result["runtime"]:
            result["runtime"]["ruby"] = m.group(1)
        gems = re.findall(r"gem\s+['\"]([^'\"]+)['\"](?:,\s*['\"]([^'\"]*)['\"])?", content)
        fw_map = {"rails": "Rails", "sinatra": "Sinatra", "hanami": "Hanami"}
        for name, ver in gems:
            if name in fw_map:
                result["frameworks"][fw_map[name]] = ver or "*"
        if gems:
            result["packages"]["gem"] = {"count": len(gems), "key": dict(gems[:10])}


def _detect_docker(root: Path, result: Dict):
    for name in ["Dockerfile", "develop.dockerfile"]:
        p = root / name
        if not p.exists(): continue
        content = p.read_text(errors="ignore")
        for m in re.finditer(r'FROM\s+([^\s]+)', content):
            image = m.group(1)
            if image.startswith("$"): continue
            if "docker_base" not in result["runtime"]:
                result["runtime"]["docker_base"] = image


# ─── LLM-assisted version enrichment ────────────────────────────────────────

_VERSION_FILES = [
    "composer.json", "composer.lock", "package.json", "package-lock.json",
    "go.mod", "go.sum", "Gemfile", "Gemfile.lock", "requirements.txt",
    "Pipfile", "pyproject.toml", "Cargo.toml", "pom.xml", "build.gradle",
    "Dockerfile", "develop.dockerfile", "docker-compose.yml",
    ".node-version", ".nvmrc", ".ruby-version", ".python-version", ".tool-versions",
]

def _enrich_versions_llm(root: Path, result: Dict, llm_fn):
    """Use LLM to extract versions from config files that regex missed."""
    snippets = []
    for name in _VERSION_FILES:
        p = root / name
        if not p.exists(): continue
        try:
            content = p.read_text(errors="ignore")
        except Exception: continue
        # Truncate large files (lockfiles)
        if len(content) > 3000:
            content = content[:3000] + "\n... (truncated)"
        snippets.append(f"### {name}\n```\n{content}\n```")

    if not snippets: return

    prompt = (
        "Analyze these project config files and extract ALL version information.\n\n"
        + "\n".join(snippets) +
        "\n\nReturn ONLY a JSON object with these keys:\n"
        '- "runtime": {"language": "version", ...} (e.g. php, node, python, go, ruby, java)\n'
        '- "frameworks": {"name": "version", ...} (e.g. Symfony, Laravel, React, Rails)\n'
        '- "tools": {"name": "version", ...} (e.g. composer, webpack, docker)\n'
        "Only include versions you can confirm from the files. Be precise."
    )

    try:
        raw = llm_fn(prompt)
        # Parse JSON from response
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        try: llm_result = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                try: llm_result = json.loads(m.group())
                except json.JSONDecodeError: return
            else: return

        # Merge LLM findings — only fill gaps, don't overwrite regex results
        for key in ("runtime", "frameworks"):
            for name, ver in llm_result.get(key, {}).items():
                name_lower = name.lower()
                if name_lower not in {k.lower() for k in result.get(key, {})}:
                    result.setdefault(key, {})[name] = str(ver)
        for name, ver in llm_result.get("tools", {}).items():
            result.setdefault("runtime", {})[name] = str(ver)
    except Exception:
        pass  # LLM failure is non-fatal
