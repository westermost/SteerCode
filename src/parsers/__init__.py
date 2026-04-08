"""
Language parsers.

To add a new language parser:
  1. Create a file in src/parsers/ (e.g. my_lang.py)
  2. Define a function: parse_mylang(content, path) -> ParseResult
  3. Register it in this __init__.py
"""

from typing import List
from ..types import ParseResult, SemanticInfo
from .python_parser import parse_python
from .regex_parser import parse_with_regex, RE_PATTERNS
from .semantics import extract_semantics

def parse_file(content: str, lang: str, path: str) -> ParseResult:
    if lang == "python": return parse_python(content, path)
    return parse_with_regex(content, lang)
