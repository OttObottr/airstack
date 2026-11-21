"""A local read-only MCP server (JSON-RPC 2.0 over stdio) over AirStack.bot's published data.

Usage: python3 -m airstack.mcp_server [data/site]
"""

import json
import sys
from pathlib import Path

from .schemas import TOOL_ARGS, SchemaError, validate

VERSION = "0.3"
PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")  # newest first
FILES = ("site-data.js", "profiles.json", "chain-data.json")
DESCRIPTIONS = {
    "search_products": "Find software products AirStack.bot tracks by name or alias. Returns ids to pass to the other tools.",
    "get_product": "A product's profile: each field's value with the pages it came from and the date they were checked.",
    "get_evidence": "Every published fact about a product: its verbatim quote, source URL, source class and the date the page was read.",
    "changes_since": "Facts whose page was read or re-checked on or after a date (YYYY-MM-DD), newest first. Pass ids to limit to a stack.",
    "review_stack": "Profiles and fact counts for a list of product ids, so a stack can be reviewed against its sources.",
}
FACT_KEYS = ("metric", "value", "quote", "url", "class", "retrieved", "verified", "first_read", "checked", "archived")
LIMIT = 200
NOT_OBSERVED = "Not observed: no fact from this product's own pages is published."


class Site:
    """The published files, read on first use and reloaded automatically when updated on disk."""

    def __init__(self, root):
        self.root = Path(root)
        self._stamp = None
        self._cache = {}

    @property
    def missing(self):
        return [name for name in FILES if not (self.root / name).exists()]

    def _json(self, name):
        return json.loads((self.root / name).read_text())

    def _get(self, key, load):
        stamp = tuple((st.st_mtime_ns, st.st_size) for name in FILES for st in ((self.root / name).stat(),))
        if stamp != self._stamp:
            self._cache.clear()
            self._stamp = stamp
        if key not in self._cache:
            self._cache[key] = load()
        return self._cache[key]

    @property
    def site_data(self):
        def load():
            text = (self.root / "site-data.js").read_text()
            return json.loads(text[text.index("{") : text.rindex("}") + 1])

        return self._get("site_data", load)

    @property
    def as_of(self):
        return (self.site_data.get("meta") or {}).get("checked_at")

    @property
    def profiles(self):
        return self._get("profiles", lambda: self._json("profiles.json"))

    @property
    def entities(self):
        return self._get("entities", lambda: self._json("chain-data.json").get("entities", {}))

    @property
    def products(self):
        """Every product with a name, as [id, name, category, aliases]: the curated index, then every product with published facts."""

        def load():
            rows = {r[0]: r for r in self.site_data.get("index", [])}
            for pid, e in self.entities.items():
                rows.setdefault(pid, [pid, e.get("name") or pid, "", []])
            return rows

        return self._get("products", load)

    @property
    def ids(self):
        """A product's id or exact name, in any case, to its id."""
        return self._get(
            "ids",
            lambda: {r[1].lower(): pid for pid, r in self.products.items()} | {pid.lower(): pid for pid in self.products},
        )

    def resolve(self, pid):
        return pid if pid in self.products else self.ids.get(pid.strip().lower(), pid)

    def facts(self, pid):
        return [{k: f.get(k) for k in FACT_KEYS} for f in self.entities.get(pid, {}).get("facts", [])]

    def search_products(self, query, limit=10):
        q = " ".join(query.split()).lower()

        def rank(r):
            names = [r[1].lower(), *(a.lower() for a in r[3])]
            return 0 if q in names else 1 if names[0].startswith(q) else 2

        hits = [r for r in self.products.values() if q in r[1].lower() or any(q in a.lower() for a in r[3])]
        hits.sort(key=lambda r: (rank(r), r[1].lower()))
        return {
            "as_of": self.as_of,
            "results": [
                {"id": r[0], "name": r[1], "category": r[2], "researched": r[0] in self.profiles} for r in hits[:limit]
            ],
        }

    def get_product(self, id):
        pid = self.resolve(id)
        if pid not in self.products:
            return {"id": pid, "known": False}
        return {
            "id": pid,
            "known": True,
            "as_of": self.as_of,
            "name": self.products[pid][1],
            "profile": self.profiles.get(pid),
            "facts": len(self.facts(pid)),
            "note": None if pid in self.profiles else NOT_OBSERVED,
        }

    def get_evidence(self, id):
        pid = self.resolve(id)
        if pid not in self.products:
            return {"id": pid, "known": False}
        return {"id": pid, "known": True, "as_of": self.as_of, "name": self.products[pid][1], "facts": self.facts(pid)}

    def changes_since(self, since, ids=None):
        def read(f):
            return max(f["verified"] or "", f["retrieved"] or "")

        wanted = {self.resolve(pid) for pid in ids} if ids is not None else None
        pids = (pid for pid in self.entities if wanted is None or pid in wanted)
        rows = [{"id": pid, **f} for pid in pids for f in self.facts(pid) if read(f) >= since]
        rows.sort(key=read, reverse=True)
        return {"since": since, "as_of": self.as_of, "total": len(rows), "facts": rows[:LIMIT], "truncated": len(rows) > LIMIT}

    def review_stack(self, ids):
        return {"as_of": self.as_of, "results": [self.get_product(pid) for pid in ids]}


def error(text):
    return {"content": [{"type": "text", "text": text}], "isError": True}


class McpServer:
    def __init__(self, root):
        self.site = Site(root)

    def call_tool(self, name, args):
        """The tool's result as MCP content. Bad arguments and a missing data folder are tool errors, so the caller can fix them."""
        if name not in TOOL_ARGS:
            raise SchemaError(f"unknown tool: {name}")
        try:
            validate(args, TOOL_ARGS[name])
        except SchemaError as e:
            return error(f"Invalid arguments: {e}")
        if self.site.missing:
            return error(
                f"No AirStack.bot data in {self.site.root}: run ./pull.sh in the repository, then call the tool again."
            )
        return {"content": [{"type": "text", "text": json.dumps(getattr(self.site, name)(**args))}]}

    def handle(self, req):
        """One JSON-RPC 2.0 message: a notification (no id) gets no response."""
        if (
            not isinstance(req, dict)
            or not isinstance(req.get("method"), str)
            or not isinstance(req.get("params", {}), dict)
        ):
            rid = req.get("id") if isinstance(req, dict) else None
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32600, "message": "invalid request"}}
        if "id" not in req:
            return None
        rid, method, params = req["id"], req["method"], req.get("params", {})
        if method == "initialize":
            asked = params.get("protocolVersion")
            res = {
                "protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
                "serverInfo": {"name": "airstack", "version": VERSION},
                "capabilities": {"tools": {}},
            }
        elif method == "ping":
            res = {}
        elif method == "tools/list":
            res = {
                "tools": [
                    {"name": n, "description": DESCRIPTIONS[n], "inputSchema": TOOL_ARGS[n]} for n in sorted(TOOL_ARGS)
                ]
            }
        elif method == "tools/call":
            try:
                res = self.call_tool(params.get("name"), params.get("arguments", {}))
            except SchemaError as e:
                return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": str(e)}}
        else:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}
        return {"jsonrpc": "2.0", "id": rid, "result": res}


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data" / "site"
    server = McpServer(root)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
        except ValueError:
            out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            try:
                out = server.handle(req)
            except Exception as e:  # one bad request never stops the server
                out = {
                    "jsonrpc": "2.0",
                    "id": req.get("id"),
                    "error": {"code": -32603, "message": f"internal error: {e}"},
                }
        if out is not None:
            print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
