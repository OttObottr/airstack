# spec: AS-040 AS-062 AS-072 AS-136 AS-294 AS-310
"""Read-only MCP tools (JSON-RPC 2.0). Takes ONLY a store: it has no path to Spark, so public tools cannot spend money."""
import json, sys
from . import views
from .config import MAX_STACK_TOOLS
from .schemas import TOOL_ARGS, SchemaError, validate

def _dispatch(store, now_fn):
    return {
        "get_verdict": lambda a: views.get_verdict(store, a["tool"], a.get("seat"), a.get("as_of"), now=now_fn()),
        "get_evidence": lambda a: views.get_evidence(store, a["tool"]),
        "changes_since": lambda a: views.changes_since(store, a["since"]),
        "review_stack": lambda a: {"results": views.review_stack(store, a["tools"], now=now_fn())},
        "get_entity": lambda a: views.get_entity(store, a["tool"]),
    }

DESCRIPTIONS = {
    "get_verdict": "Current dated verdict (BUILD, BUY, KEEP or RETIRE) for a software tool, optionally for a named seat, with the evidence URLs, "
                   "the facts it depends on and the conditions that would change it. A LAPSED verdict is never current advice. "
                   "Call this before advising whether to keep, drop or buy a tool.",
    "get_evidence": "Every dated, sourced fact recorded about a software tool, with its source URL, publication time and observation time.",
    "changes_since": "Facts recorded and verdicts lapsed or superseded since a date. Use it to find software advice that has gone out of date.",
    "review_stack": "Evaluate a list of tools against stated seat requirements, returning pass, fail or unknown for each requirement. Computed in code; no model call.",
    "get_entity": "Basic record for a software tool known to the database.",
}

class McpServer:
    def __init__(self, store, now_fn=None):
        from .store import utcnow
        self._tools = _dispatch(store, now_fn or utcnow)
    @property
    def tool_names(self):
        return sorted(self._tools)
    def call_tool(self, name, args):
        if name not in self._tools:
            raise KeyError(name)
        validate(args, TOOL_ARGS[name])
        if name == "review_stack" and len(args["tools"]) > MAX_STACK_TOOLS:
            raise SchemaError(f"a stack review takes at most {MAX_STACK_TOOLS} tools")
        return self._tools[name](args)
    def handle(self, req):
        """JSON-RPC 2.0: a message without an id is a NOTIFICATION and never gets a response."""
        if "id" not in req:
            return None
        rid, method = req.get("id"), req.get("method")
        try:
            if method == "initialize":
                res = {"protocolVersion": "2024-11-05", "serverInfo": {"name": "airstack", "version": "0.1"}, "capabilities": {"tools": {}}}
            elif method == "tools/list":
                res = {"tools": [{"name": n, "description": DESCRIPTIONS[n], "inputSchema": TOOL_ARGS[n]} for n in self.tool_names]}
            elif method == "tools/call":
                p = req.get("params", {})
                out = self.call_tool(p.get("name"), p.get("arguments", {}))
                res = {"content": [{"type": "text", "text": json.dumps(out)}]}
            else:
                return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}
            return {"jsonrpc": "2.0", "id": rid, "result": res}
        except (SchemaError, KeyError) as e:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": str(e)}}

def main():                                           # stdio transport: python -m airstack.mcp_server <db path>
    from .store import Store
    srv = McpServer(Store(sys.argv[1] if len(sys.argv) > 1 else "airstack.db"))
    for line in sys.stdin:
        if line.strip():
            out = srv.handle(json.loads(line))
            if out is not None:
                sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()

if __name__ == "__main__":
    main()
