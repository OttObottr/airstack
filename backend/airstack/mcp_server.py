"""A local read-only MCP server (JSON-RPC 2.0 over stdio) over the published datasets.
Usage: python -m airstack.mcp_server [data/site directory]"""
import functools
import json
import re
import sys
from pathlib import Path
from .schemas import TOOL_ARGS, SchemaError, validate

DESCRIPTIONS = {
    "search_products": "Find software products AirStack tracks by name or alias. Returns ids to pass to the other tools.",
    "get_product": "A product's profile: each field's value with the pages it came from and the date they were checked.",
    "get_evidence": "Every published fact about a product, each with its verbatim quote, source URL, source class and the date the page was read.",
    "changes_since": "Facts whose page was read or re-checked on or after a date (YYYY-MM-DD), newest first.",
    "review_stack": "Profiles and fact counts for a list of product ids, so a stack can be reviewed against its sources. No recommendation is made.",
}
FACT_KEYS = ("metric", "value", "quote", "url", "class", "retrieved", "verified", "first_read", "checked", "archived")
LIMIT = 200


class Site:
    """The published datasets, each read on first use."""
    def __init__(self, root):
        self.root = Path(root)
    def _json(self, name):
        p = self.root / name
        return json.loads(p.read_text()) if p.exists() else {}
    @functools.cached_property
    def profiles(self): return self._json("profiles.json")
    @functools.cached_property
    def entities(self): return self._json("chain-data.json").get("entities", {})
    @functools.cached_property
    def index(self):
        p = self.root / "site-data.js"
        if not p.exists():
            return []
        text = p.read_text()
        return json.loads(text[text.index("{"):text.rindex("}") + 1]).get("index", [])

    def facts(self, pid):
        return [{k: f.get(k) for k in FACT_KEYS} for f in self.entities.get(pid, {}).get("facts", [])]
    def name(self, pid):
        return self.entities.get(pid, {}).get("name") or next((r[1] for r in self.index if r[0] == pid), None)

    def search_products(self, query, limit=10):
        q = re.sub(r"\s+", " ", query).strip().lower()
        rank = lambda r: 0 if r[1].lower() == q or q in (a.lower() for a in r[3]) else 1 if r[1].lower().startswith(q) else 2
        hits = [r for r in self.index if q in r[1].lower() or any(q in a.lower() for a in r[3])]
        return {"results": [{"id": r[0], "name": r[1], "category": r[2], "researched": r[0] in self.profiles} for r in sorted(hits, key=rank)[:limit]]}
    def get_product(self, pid):
        name = self.name(pid)
        if name is None:
            return {"id": pid, "known": False}
        return {"id": pid, "known": True, "name": name, "profile": self.profiles.get(pid), "facts": len(self.facts(pid)),
                "note": None if pid in self.profiles else "Not observed: no fact from this product's own pages is published."}
    def get_evidence(self, pid):
        return {"id": pid, "name": self.name(pid), "facts": self.facts(pid)}
    def changes_since(self, since):
        rows = [{"id": pid, **f} for pid in self.entities for f in self.facts(pid) if max(f["verified"] or "", f["retrieved"] or "") >= since]
        rows.sort(key=lambda f: max(f["verified"] or "", f["retrieved"] or ""), reverse=True)
        return {"since": since, "total": len(rows), "facts": rows[:LIMIT], "truncated": len(rows) > LIMIT}
    def review_stack(self, ids):
        return {"results": [self.get_product(pid) for pid in ids]}


class McpServer:
    def __init__(self, root):
        site = Site(root)
        self._tools = {
            "search_products": lambda a: site.search_products(a["query"], a.get("limit", 10)),
            "get_product": lambda a: site.get_product(a["id"]),
            "get_evidence": lambda a: site.get_evidence(a["id"]),
            "changes_since": lambda a: site.changes_since(a["since"]),
            "review_stack": lambda a: site.review_stack(a["ids"]),
        }
    @property
    def tool_names(self):
        return sorted(self._tools)
    def call_tool(self, name, args):
        if name not in self._tools:
            raise KeyError(name)
        validate(args, TOOL_ARGS[name])
        return self._tools[name](args)
    def handle(self, req):
        """JSON-RPC 2.0: a notification (no id) gets no response; a request that is not an object with a method is invalid."""
        if not isinstance(req, dict) or not isinstance(req.get("method"), str) or not isinstance(req.get("params", {}), dict):
            return {"jsonrpc": "2.0", "id": req.get("id") if isinstance(req, dict) else None, "error": {"code": -32600, "message": "invalid request"}}
        if "id" not in req:
            return None
        rid, method = req.get("id"), req.get("method")
        try:
            if method == "initialize":
                res = {"protocolVersion": "2024-11-05", "serverInfo": {"name": "airstack", "version": "0.2"}, "capabilities": {"tools": {}}}
            elif method == "tools/list":
                res = {"tools": [{"name": n, "description": DESCRIPTIONS[n], "inputSchema": TOOL_ARGS[n]} for n in self.tool_names]}
            elif method == "tools/call":
                p = req.get("params", {})
                res = {"content": [{"type": "text", "text": json.dumps(self.call_tool(p.get("name"), p.get("arguments", {})))}]}
            else:
                return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}
            return {"jsonrpc": "2.0", "id": rid, "result": res}
        except (SchemaError, KeyError, TypeError) as e:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": str(e)}}


def main():
    from . import paths
    srv = McpServer(sys.argv[1] if len(sys.argv) > 1 else paths.SITE)
    for line in sys.stdin:
        if line.strip():
            try:
                req = json.loads(line)
            except ValueError:
                out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
            else:
                out = srv.handle(req)
            if out is not None:
                sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()

if __name__ == "__main__":
    main()
