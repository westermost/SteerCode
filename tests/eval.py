"""Evaluation framework for SteerCode graph quality."""

import json, sys
from pathlib import Path

GOLDEN_TESTS = [
    {
        "name": "_llm_request",
        "expected_effects": ["external_api"],
        "expected_control": ["try_catch"],
    },
    {
        "name": "scan_files",
        "expected_control": ["branching", "loop"],
    },
    {
        "name": "extract_semantics",
        "expected_control": ["branching", "loop"],
    },
    {
        "name": "compute_importance",
        "expected_effects": [],
        "expected_control": ["branching", "loop"],
    },
    {
        "name": "normalize_entity",
        "expected_role": "data_access",
    },
]


def eval_node(node: dict, test: dict) -> dict:
    # Support both nested semantics and flattened format
    sem = node.get("semantics", {})
    scores = {}

    if "expected_effects" in test:
        # Flattened: node["effects"] = ["external_api", ...]
        # Nested: node["semantics"]["side_effects"] = [{"type": "external_api", ...}]
        if "effects" in node:
            actual = {e.split(":")[0] for e in node["effects"]}
        else:
            actual = {e["type"].split(":")[0] if isinstance(e, dict) else e.split(":")[0]
                      for e in sem.get("side_effects", [])}
        expected = set(test["expected_effects"])
        if expected:
            scores["effects"] = len(actual & expected) / len(expected)
        else:
            scores["effects"] = 1.0 if not actual else 0.5

    if "expected_control" in test:
        actual = set(sem.get("control_flow", []) or node.get("control_flow", []))
        expected = set(test["expected_control"])
        scores["control"] = len(actual & expected) / max(len(expected), 1)

    if "expected_role" in test:
        role = sem.get("execution_role", "") or node.get("role", "")
        scores["role"] = 1.0 if role == test["expected_role"] else 0.0

    avg = sum(scores.values()) / max(len(scores), 1)
    return {"name": test["name"], "score": round(avg, 2), **scores}


def eval_graph(graph_path: str, tests: list = None) -> dict:
    tests = tests or GOLDEN_TESTS
    data = json.loads(Path(graph_path).read_text())
    nodes = {n["name"]: n for n in data["nodes"]}

    results = []
    for test in tests:
        node = nodes.get(test["name"])
        if not node:
            results.append({"name": test["name"], "score": 0, "reason": "not found"})
            continue
        results.append(eval_node(node, test))

    overall = sum(r["score"] for r in results) / max(len(results), 1)
    return {"overall": round(overall, 2), "results": results}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else ".codemap-output/knowledge-graph.json"
    result = eval_graph(path)
    print(json.dumps(result, indent=2))
    print(f"\nOverall score: {result['overall']}")
