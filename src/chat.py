"""Chat mode — interactive Q&A about codebase using knowledge graph + LLM."""

import json
from pathlib import Path
from typing import Optional
from .query import GraphQuery
from .llm import _llm_request, _extract_json


class ChatSession:
    def __init__(self, graph_path: str, llm_url: str, model: str = ""):
        self.query = GraphQuery(graph_path)
        self.llm_url = llm_url
        self.model = model
        self.graph_data = json.loads(Path(graph_path).read_text())
        self.history = []

    def ask(self, question: str) -> str:
        """Search graph for relevant nodes, build context, ask LLM."""
        # Search by keywords in question
        words = [w for w in question.lower().split() if len(w) >= 3]
        relevant = set()
        for w in words:
            for n in self.query.find(name=w):
                relevant.add(n["id"])
            for n in self.query.find(domain=w):
                relevant.add(n["id"])
            for n in self.query.find(effect=w):
                relevant.add(n["id"])

        # Expand 1-hop
        expanded = set()
        for nid in relevant:
            for e in self.query.edges:
                if e["type"] not in ("calls", "imports"): continue
                if e["source"] == nid and e["target"] in self.query.nodes: expanded.add(e["target"])
                if e["target"] == nid and e["source"] in self.query.nodes: expanded.add(e["source"])
        relevant |= expanded

        # Build context
        nodes = [self.query.nodes[nid] for nid in relevant if nid in self.query.nodes][:30]
        context = self._format_context(nodes)

        prompt = (
            f"You are a codebase expert. Answer based ONLY on the context below.\n\n"
            f"=== Codebase Context ===\n{context}\n\n"
            f"=== Question ===\n{question}\n\n"
            f"Answer concisely. Reference specific functions/files when relevant."
        )

        try:
            return _llm_request(self.llm_url, self.model, prompt)
        except Exception as e:
            return f"LLM error: {e}"

    def _format_context(self, nodes: list) -> str:
        lines = [f"Project: {self.graph_data['project']['name']}",
                 f"Languages: {', '.join(self.graph_data['project'].get('languages', [])[:5])}", ""]
        for n in nodes:
            parts = [f"{n['name']} ({n.get('type', '')})"]
            if n.get("file_path"): parts.append(f"in {n['file_path']}")
            if n.get("summary"): parts.append(f"— {n['summary'][:100]}")
            if n.get("domain"): parts.append(f"[{n['domain']}]")
            if n.get("effects"): parts.append(f"effects: {', '.join(n['effects'][:3])}")
            lines.append("  ".join(parts))
        return "\n".join(lines)
