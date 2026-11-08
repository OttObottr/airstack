"""The local MCP server: read-only, facts with their quotes, no recommendation, no network."""
import ast
import json
import pathlib
import re
import subprocess
import sys
import pytest
from airstack import paths
from airstack.mcp_server import DESCRIPTIONS, McpServer
from airstack.schemas import SchemaError

FACT = {"metric": "integrations", "value": ["Service A"], "url": "https://acme.test/integrations", "host": "acme.test", "class": "vendor",
        "quote": "Works with Service A", "retrieved": "2026-11-04", "verified": "2026-11-05", "status": 200}

@pytest.fixture
def site(tmp_path):
    (tmp_path / "chain-data.json").write_text(json.dumps({"entities": {"acme": {"name": "Acme", "facts": [FACT, {**FACT, "verified": "2026-10-01", "retrieved": "2026-10-01"}]}}}))
    (tmp_path / "profiles.json").write_text(json.dumps({"acme": {"integrations": {"value": ["Service A"], "sources": [{"url": FACT["url"]}], "checked": "2026-11-04"}, "facts": 2}}))
    (tmp_path / "site-data.js").write_text("window.AIRSTACK_DATA = " + json.dumps({"index": [["acme", "Acme", "crm", ["Acme CRM"]], ["beta", "Beta", "crm", []]]}) + ";\n")
    return McpServer(tmp_path)

def test_every_tool_is_described_and_no_description_gives_a_verdict(site):
    assert site.tool_names == sorted(DESCRIPTIONS)
    assert not [n for n, d in DESCRIPTIONS.items() if re.search(r"\b(BUILD|BUY|KEEP|RETIRE|verdict)\b", d, re.I)]

def test_a_fact_carries_its_quote_page_and_read_date_and_unknown_stays_unknown(site):
    assert site.call_tool("search_products", {"query": "acme crm"})["results"][0]["id"] == "acme"
    ev = site.call_tool("get_evidence", {"id": "acme"})["facts"][0]
    assert ev["quote"] == "Works with Service A" and ev["url"].startswith("https://") and ev["retrieved"] == "2026-11-04"
    beta = site.call_tool("get_product", {"id": "beta"})
    assert beta["known"] and beta["profile"] is None and beta["facts"] == 0 and beta["note"].startswith("Not observed")
    assert site.call_tool("get_product", {"id": "nobody"}) == {"id": "nobody", "known": False}

def test_changes_since_returns_only_facts_read_on_or_after_the_date(site):
    out = site.call_tool("changes_since", {"since": "2026-11-01"})
    assert out["total"] == 1 and out["facts"][0]["verified"] == "2026-11-05"

def test_a_stack_review_is_bounded_and_arguments_are_validated(site):
    assert len(site.call_tool("review_stack", {"ids": ["acme"] * 25})["results"]) == 25
    with pytest.raises(SchemaError):
        site.call_tool("review_stack", {"ids": ["acme"] * 26})
    with pytest.raises(SchemaError):
        site.call_tool("get_product", {"id": "../etc/passwd"})

def test_notifications_get_no_response(site):
    assert site.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert site.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["id"] == 1

def test_the_stdio_loop_answers_over_the_published_datasets():
    msgs = '{"jsonrpc":"2.0","method":"notifications/initialized"}\n' \
           '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_products","arguments":{"query":"ai","limit":1}}}\n'
    out = subprocess.run([sys.executable, "-m", "airstack.mcp_server", str(paths.SITE)], input=msgs,
                         capture_output=True, text=True, cwd=paths.ROOT / "backend", timeout=60).stdout.strip().splitlines()
    assert len(out) == 1 and json.loads(out[0])["id"] == 2 and "result" in json.loads(out[0])

def test_malformed_input_gets_a_json_rpc_error_not_a_crash():
    msgs = 'not json\n[1]\n{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_product","arguments":[]}}\n{"jsonrpc":"2.0","id":4,"method":"tools/list"}\n'
    out = [json.loads(line) for line in subprocess.run([sys.executable, "-m", "airstack.mcp_server", str(paths.SITE)], input=msgs, capture_output=True,
                                                         text=True, cwd=paths.ROOT / "backend", timeout=60).stdout.splitlines()]
    assert [o.get("error", {}).get("code") for o in out] == [-32700, -32600, -32602, None] and out[3]["id"] == 4

def test_the_server_cannot_open_a_network_connection_or_a_database():
    tree = ast.parse((pathlib.Path(paths.ROOT) / "backend" / "airstack" / "mcp_server.py").read_text())
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not {m for m in mods if m.split(".")[0] in {"socket", "urllib", "http", "sqlite3", "fetch", "requests"}}, mods
