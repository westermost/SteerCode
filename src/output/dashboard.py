"""Dashboard HTML generation."""

import json
from pathlib import Path


def _strip_defaults(graph_data: dict) -> dict:
    """Remove empty/default fields to reduce JSON size."""
    stripped = {**graph_data}
    stripped["nodes"] = []
    for n in graph_data["nodes"]:
        node = {k: v for k, v in n.items()
                if v and v != [] and v != (0, 0) and v != [0, 0] and v != "simple"}
        if n.get("complexity") and n["complexity"] != "simple":
            node["complexity"] = n["complexity"]
        stripped["nodes"].append(node)
    stripped["edges"] = []
    for e in graph_data["edges"]:
        edge = {"source": e["source"], "target": e["target"], "type": e["type"]}
        if e.get("weight", 0.5) != 0.5: edge["weight"] = e["weight"]
        stripped["edges"].append(edge)
    return stripped


def generate_dashboard(graph_data: dict, output_dir: Path):
    dashboard_dir = Path(__file__).parent.parent.parent / "dashboard"
    template = (dashboard_dir / "template.html").read_text(encoding="utf-8")
    css = (dashboard_dir / "style.css").read_text(encoding="utf-8")
    js = (dashboard_dir / "app.js").read_text(encoding="utf-8")
    i18n = (dashboard_dir / "i18n.js").read_text(encoding="utf-8")

    output_dir.mkdir(parents=True, exist_ok=True)

    compact = _strip_defaults(graph_data)

    kg_path = output_dir / "knowledge-graph.json"
    kg_path.write_text(json.dumps(compact, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    graph_json = json.dumps(graph_data, ensure_ascii=False, separators=(",", ":"))
    (output_dir / "data.js").write_text(f"const GRAPH_DATA={graph_json};", encoding="utf-8")

    html = template.replace("{{CSS}}", css).replace("{{I18N}}", i18n).replace("{{JS}}", js)
    html = html.replace("{{PROJECT_NAME}}", graph_data["project"]["name"])
    dash_path = output_dir / "dashboard.html"
    dash_path.write_text(html, encoding="utf-8")

    return dash_path, kg_path
