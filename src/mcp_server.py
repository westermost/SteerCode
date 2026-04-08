"""SteerCode MCP Server — expose knowledge graph queries via Model Context Protocol."""

import json, sys
from pathlib import Path
from .query import GraphQuery


def handle_request(request: dict, query: GraphQuery) -> dict:
    """Handle a single MCP tool call."""
    name = request.get("name", "")
    args = request.get("arguments", {})

    if name == "steercode_find":
        results = query.find(
            node_type=args.get("type"), domain=args.get("domain"),
            effect=args.get("effect"), name=args.get("name"))
        return {"content": [{"type": "text", "text": json.dumps(
            [{"name": n["name"], "type": n["type"], "file": n.get("file_path", ""),
              "domain": n.get("domain"), "effects": n.get("effects", [])}
             for n in results[:50]], indent=2)}]}

    elif name == "steercode_impact":
        results = query.impact(args.get("node", ""), args.get("depth", 2))
        return {"content": [{"type": "text", "text": json.dumps(
            [{"name": n["name"], "type": n["type"], "file": n.get("file_path", "")}
             for n in results], indent=2)}]}

    elif name == "steercode_flow":
        path = query.flow(args.get("from", ""), args.get("to", ""))
        names = [n["name"] for n in path]
        return {"content": [{"type": "text", "text": " → ".join(names) if names else "No path found"}]}

    elif name == "steercode_explain":
        info = query.explain(args.get("node", ""))
        return {"content": [{"type": "text", "text": json.dumps(info, indent=2) if info else "Node not found"}]}

    return {"error": {"code": -1, "message": f"Unknown tool: {name}"}}


TOOLS = [
    {"name": "steercode_find", "description": "Find functions/classes by type, domain, side effect, or name",
     "inputSchema": {"type": "object", "properties": {
         "type": {"type": "string", "description": "Node type: function, class, file"},
         "domain": {"type": "string", "description": "Business domain: payment, auth, user, email, storage, search, admin"},
         "effect": {"type": "string", "description": "Side effect: db_write, db_read, external_api, file_io, state_mutate"},
         "name": {"type": "string", "description": "Name substring to search"}}}},
    {"name": "steercode_impact", "description": "Find all nodes impacted if a function changes",
     "inputSchema": {"type": "object", "properties": {
         "node": {"type": "string", "description": "Function/class name"},
         "depth": {"type": "integer", "description": "Max BFS depth (default 2)"}}, "required": ["node"]}},
    {"name": "steercode_flow", "description": "Trace execution path between two functions",
     "inputSchema": {"type": "object", "properties": {
         "from": {"type": "string"}, "to": {"type": "string"}}, "required": ["from", "to"]}},
    {"name": "steercode_explain", "description": "Get full context for a function: summary, callers, callees, effects",
     "inputSchema": {"type": "object", "properties": {
         "node": {"type": "string", "description": "Function/class name"}}, "required": ["node"]}},
]


def run_stdio():
    """Run MCP server over stdio (JSON-RPC)."""
    graph_path = Path(".codemap-output/knowledge-graph.json")
    if not graph_path.exists():
        sys.stderr.write("Error: No knowledge graph found. Run 'python steercode.py .' first.\n")
        sys.exit(1)

    query = GraphQuery(str(graph_path))
    sys.stderr.write(f"SteerCode MCP server ready ({len(query.nodes)} nodes)\n")

    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method", "")
        mid = msg.get("id")

        if method == "initialize":
            resp = {"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "steercode", "version": "1.0.0"}}}

        elif method == "notifications/initialized":
            continue

        elif method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}

        elif method == "tools/call":
            params = msg.get("params", {})
            result = handle_request(params, query)
            resp = {"jsonrpc": "2.0", "id": mid, "result": result}

        else:
            resp = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Unknown method: {method}"}}

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    run_stdio()
