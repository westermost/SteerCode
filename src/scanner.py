import fnmatch, hashlib, json
from pathlib import Path
from typing import List, Dict, Optional

DEFAULT_IGNORE = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "out", ".cache", "target", ".next", ".nuxt",
    ".codemap-output", "steercode", ".idea", ".vs",
    "vendor", "Pods", ".gradle", "coverage",
    ".tox", ".mypy_cache", ".pytest_cache",
    "storage", "bootstrap/cache", "var/cache", "tmp", "temp", "logs",
    "cache", ".sass-cache", ".parcel-cache",
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".o", ".a",
    ".class", ".jar", ".war", ".map", ".lock", ".min.js", ".min.css",
    ".woff", ".woff2", ".ttf", ".eot", ".ico", ".png", ".jpg", ".jpeg",
    ".gif", ".svg", ".mp3", ".mp4", ".zip", ".tar", ".gz", ".pdf",
}

LANG_MAP = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".mts": "typescript",
    ".java": "java", ".go": "go", ".rs": "rust",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp",
    ".cs": "csharp",
    ".rb": "ruby", ".erb": "ruby",
    ".php": "php", ".phtml": "php", ".blade.php": "php",
    ".swift": "swift", ".kt": "kotlin", ".kts": "kotlin", ".scala": "scala",
    ".r": "r", ".R": "r", ".lua": "lua",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".sql": "sql",
    ".html": "html", ".htm": "html", ".twig": "html", ".hbs": "html",
    ".vue": "html", ".svelte": "html", ".ejs": "html", ".pug": "html",
    ".css": "css", ".scss": "css", ".less": "css", ".sass": "css",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".xml": "xml", ".xsl": "xml", ".xslt": "xml",
    ".md": "markdown", ".mdx": "markdown", ".rst": "markdown",
    ".dockerfile": "dockerfile", ".tf": "terraform",
    ".proto": "protobuf", ".graphql": "graphql", ".gql": "graphql",
    ".env": "shell", ".htaccess": "shell",
    ".ini": "toml", ".cfg": "toml", ".conf": "yaml",
}

CODE_LANGS = {"python","javascript","typescript","java","go","rust","c","cpp",
              "csharp","ruby","php","swift","kotlin","scala","lua","shell"}

MAX_FILE_SIZE = 512 * 1024

def parse_gitignore(root: Path) -> List[str]:
    gi = root / ".gitignore"
    if not gi.exists():
        return []
    return [l.strip() for l in gi.read_text(errors="ignore").splitlines()
            if l.strip() and not l.strip().startswith("#")]

def is_ignored(path: Path, root: Path, gi_patterns: List[str]) -> bool:
    rel = str(path.relative_to(root))
    name = path.name
    if name in DEFAULT_IGNORE:
        return True
    if path.is_dir() and name.startswith("."):
        return True
    if path.suffix.lower() in IGNORE_EXTENSIONS:
        return True
    # Multi-part extensions (.min.js, .min.css, etc.)
    name_lower = name.lower()
    if any(name_lower.endswith(ext) for ext in IGNORE_EXTENSIONS):
        return True
    for pat in gi_patterns:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel, pat):
            return True
        if pat.endswith("/") and fnmatch.fnmatch(name, pat.rstrip("/")):
            return True
    return False

def detect_language(path: Path) -> str:
    name = path.name.lower()
    if name == "dockerfile": return "dockerfile"
    if name == "makefile": return "makefile"
    for ext, lang in LANG_MAP.items():
        if name.endswith(ext):
            return lang
    return LANG_MAP.get(path.suffix.lower(), "")

def scan_files(root: Path, on_progress=None) -> List[Path]:
    gi_patterns = parse_gitignore(root)
    files = []
    def walk(d: Path):
        try:
            entries = sorted(d.iterdir())
        except PermissionError:
            return
        for e in entries:
            if is_ignored(e, root, gi_patterns):
                continue
            if e.is_dir():
                walk(e)
            elif e.is_file() and e.stat().st_size <= MAX_FILE_SIZE:
                if detect_language(e):
                    files.append(e)
                    if on_progress:
                        on_progress(len(files), e.name)
    walk(root)
    return files


# ─── Fingerprints (Incremental) ──────────────────────────────────────────────

def compute_fingerprints(root: Path, files: List[Path]) -> Dict[str, str]:
    """Fast fingerprint: size + mtime (no file read needed)."""
    fps = {}
    for f in files:
        try:
            st = f.stat()
            fps[str(f.relative_to(root)).replace("\\", "/")] = f"{st.st_size}:{int(st.st_mtime)}"
        except Exception:
            pass
    return fps


def diff_fingerprints(old: Dict[str, str], new: Dict[str, str]) -> Dict[str, List[str]]:
    """Compare fingerprints. Returns {added, modified, removed}."""
    old_keys, new_keys = set(old), set(new)
    return {
        "added": sorted(new_keys - old_keys),
        "modified": sorted(k for k in old_keys & new_keys if old[k] != new[k]),
        "removed": sorted(old_keys - new_keys),
    }


def load_fingerprints(path: Path) -> Optional[Dict[str, str]]:
    if path.exists():
        try: return json.loads(path.read_text())
        except Exception: pass
    return None


def save_fingerprints(fps: Dict[str, str], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fps, indent=2))
