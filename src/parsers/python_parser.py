"""Python AST-based parser."""

import ast as python_ast
from ..types import ParseResult


def parse_python(content: str, path: str) -> ParseResult:
    r = ParseResult()
    try:
        tree = python_ast.parse(content, filename=path)
    except SyntaxError:
        return r
    for node in python_ast.walk(tree):
        if isinstance(node, (python_ast.FunctionDef, python_ast.AsyncFunctionDef)):
            params = [a.arg for a in node.args.args if a.arg != "self"]
            decos = []
            for d in node.decorator_list:
                if isinstance(d, python_ast.Name): decos.append(d.id)
                elif isinstance(d, python_ast.Attribute): decos.append(d.attr)
            r.functions.append({"name": node.name, "line_start": node.lineno,
                "line_end": node.end_lineno or node.lineno, "params": params, "decorators": decos})
        elif isinstance(node, python_ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, (python_ast.FunctionDef, python_ast.AsyncFunctionDef))]
            bases = []
            for b in node.bases:
                if isinstance(b, python_ast.Name): bases.append(b.id)
                elif isinstance(b, python_ast.Attribute): bases.append(b.attr)
            decos = [d.id for d in node.decorator_list if isinstance(d, python_ast.Name)]
            r.classes.append({"name": node.name, "line_start": node.lineno,
                "line_end": node.end_lineno or node.lineno, "methods": methods, "bases": bases, "decorators": decos})
        elif isinstance(node, python_ast.Import):
            for alias in node.names:
                r.imports.append({"source": alias.name, "specifiers": [alias.asname or alias.name], "line": node.lineno})
        elif isinstance(node, python_ast.ImportFrom):
            r.imports.append({"source": node.module or "", "specifiers": [a.name for a in node.names], "line": node.lineno})
    return r
