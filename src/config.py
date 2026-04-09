"""Configuration loader — merges defaults with user overrides."""

import json
from pathlib import Path

DEFAULTS = {
    "llm": {
        "timeout": 300,
        "max_retries": 3,
        "max_workers": 3,
        "max_code_chars": 15000,
        "files_per_batch": 15,
        "nodes_per_batch": 30,
        "snippet_max_chars": 3000,
        "top_k_callers": 2,
        "top_k_callees": 3,
    },
    "scan": {
        "max_file_size_kb": 512,
        "progress_throttle": 50,
    },
}

_config = None

def load_config(root: Path = None) -> dict:
    """Load config: project steercode.config.json → merge with defaults."""
    global _config
    if _config is not None:
        return _config
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    for p in [root / "steercode.config.json" if root else None, Path("steercode.config.json")]:
        if p and p.exists():
            try:
                user = json.loads(p.read_text())
                for section, values in user.items():
                    if section in cfg and isinstance(values, dict):
                        cfg[section].update(values)
            except Exception:
                pass
            break
    _config = cfg
    return cfg

def get(section: str, key: str):
    cfg = load_config()
    return cfg.get(section, {}).get(key, DEFAULTS.get(section, {}).get(key))

def reset():
    global _config
    _config = None
