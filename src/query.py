"""Query engine for knowledge graph — find, impact, flow, explain."""

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import List, Dict, Optional, Set


class GraphQuery:
    """Query interface over SteerCode knowledge graph."""

    def __init__(self, graph_path: str):
        data = json.loads(Path(graph_path).read_text())
        self.nodes = {n["id"]: n for n in data["nodes"]}
        self.edges = data["edges"]
        self._by_name = {}
        self._index = {"domain": defaultdict(set), "effect": defaultdict(set),
                       "role": defaultdict(set), "type": defaultdict(set)}
        for nid, n in self.nodes.items():
            self._by_name[n["name"]] = nid
            self._index["type"][n.get("type", "")].add(nid)
            if n.get("domain"): self._index["domain"][n["domain"]].add(nid)
            if n.get("role"): self._index["role"][n["role"]].add(nid)
            for eff in n.get("effects", []):
                self._index["effect"][eff.split(":")[0]].add(nid)
                self._index["effect"][eff].add(nid)

    def find(self, node_type=None, domain=None, effect=None, name=None) -> List[dict]:
        """Find nodes by filters. O(1) for indexed fields."""
        candidates = set(self.nodes.keys())
        if node_type: candidates &= self._index["type"].get(node_type, set())
        if domain: candidates &= self._index["domain"].get(domain, set())
        if effect: candidates &= self._index["effect"].get(effect, set())
        results = [self.nodes[nid] for nid in candidates]
        if name:
            q = name.lower()
            results = [n for n in results if q in n["name"].lower()]
        return results

    def impact(self, node_name: str, max_depth: int = 2) -> List[dict]:
        """What breaks if this node changes? Bounded BFS."""
        nid = self._by_name.get(node_name)
        if not nid: return []
        visited = {nid}
        frontier = {nid}
        for _ in range(max_depth):
            next_f = set()
            for f in frontier:
                for e in self.edges:
                    if e["type"] not in ("calls", "imports"): continue
                    nb = e["target"] if e["source"] == f else (e["source"] if e["target"] == f else None)
                    if nb and nb not in visited:
                        visited.add(nb)
                        next_f.add(nb)
            frontier = next_f
            if not frontier: break
        return [self.nodes[nid] for nid in visited if nid in self.nodes]

    def flow(self, from_name: str, to_name: str) -> List[dict]:
        """Trace shortest execution path between two nodes."""
        src = self._by_name.get(from_name)
        dst = self._by_name.get(to_name)
        if not src or not dst: return []

        # Build adjacency for calls edges
        adj = defaultdict(set)
        for e in self.edges:
            if e["type"] == "calls":
                adj[e["source"]].add(e["target"])
                adj[e["target"]].add(e["source"])

        # BFS
        queue = deque([(src, [src])])
        visited = {src}
        while queue:
            current, path = queue.popleft()
            if current == dst:
                return [self.nodes[nid] for nid in path if nid in self.nodes]
            for nb in adj.get(current, set()):
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, path + [nb]))
        return []

    def explain(self, node_name: str, root: Path = None) -> Optional[dict]:
        """Full context for a node, including source code."""
        nid = self._by_name.get(node_name)
        if not nid or nid not in self.nodes: return None
        n = self.nodes[nid]
        callers = [self.nodes[e["source"]]["name"] for e in self.edges
                   if e["target"] == nid and e["type"] == "calls" and e["source"] in self.nodes]
        callees = [self.nodes[e["target"]]["name"] for e in self.edges
                   if e["source"] == nid and e["type"] == "calls" and e["target"] in self.nodes]
        # Read source code
        source_lines = []
        if root and n.get("file_path"):
            try:
                fp = root / n["file_path"]
                lines = fp.read_text(errors="ignore").splitlines()
                lr = n.get("line_range", [0, 0])
                if lr[0] > 0:
                    s, e = max(0, lr[0] - 1), min(len(lines), lr[1])
                    source_lines = [(lr[0] + i, lines[s + i]) for i in range(e - s)]
            except Exception:
                pass
        return {
            "name": n["name"], "type": n.get("type"), "file": n.get("file_path"),
            "line_range": n.get("line_range"), "summary": n.get("summary", ""),
            "complexity": n.get("complexity"), "domain": n.get("domain"),
            "role": n.get("role"), "effects": n.get("effects", []),
            "control_flow": n.get("control_flow", []), "importance": n.get("importance"),
            "callers": callers, "callees": callees, "source": source_lines,
        }
