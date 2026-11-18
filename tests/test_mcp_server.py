import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from airstack.mcp_server import PROTOCOLS, McpServer

ROOT = Path(__file__).resolve().parents[1]
FACT = {
    "metric": "free_plan",
    "value": True,
    "quote": "Free for individuals",
    "url": "https://acme.example/pricing",
    "class": "vendor",
}


def write_site(root):
    index = {"index": [["acme", "Acme Docs", "docs", ["acmedocs"]], ["beta", "Beta Chat", "chat", []]]}
    (root / "site-data.js").write_text(f"window.AIRSTACK_DATA = {json.dumps(index)};\n")
    (root / "profiles.json").write_text(json.dumps({"acme": {"free_plan": {"value": True}}}))
    entities = {
        "acme": {"name": "Acme Docs", "facts": [{**FACT, "retrieved": "2026-11-01", "verified": "2026-11-02"}]},
        "gamma": {
            "name": "Gamma",
            "facts": [{**FACT, "url": "https://gamma.example/", "retrieved": "2026-10-01", "verified": None}],
        },
    }
    (root / "chain-data.json").write_text(json.dumps({"entities": entities}))


class Server(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_site(self.root)
        self.server = McpServer(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def rpc(self, method, params=None, rid=1):
        return self.server.handle({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})

    def call(self, name, **args):
        res = self.rpc("tools/call", {"name": name, "arguments": args})["result"]
        text = res["content"][0]["text"]
        return (text, True) if res.get("isError") else (json.loads(text), False)

    def test_initialize_answers_with_the_clients_version_when_supported(self):
        for asked, want in [("2025-06-18", "2025-06-18"), ("2024-11-05", "2024-11-05"), ("1999-01-01", PROTOCOLS[0])]:
            self.assertEqual(self.rpc("initialize", {"protocolVersion": asked})["result"]["protocolVersion"], want)

    def test_tools_are_listed_in_a_stable_order_with_their_schemas(self):
        tools = self.rpc("tools/list")["result"]["tools"]
        self.assertEqual(
            [t["name"] for t in tools],
            ["changes_since", "get_evidence", "get_product", "review_stack", "search_products"],
        )
        self.assertTrue(all(t["description"] and t["inputSchema"]["type"] == "object" for t in tools))

    def test_search_finds_by_name_and_alias_with_exact_matches_first(self):
        self.assertEqual([r["id"] for r in self.call("search_products", query="acmedocs")[0]["results"]], ["acme"])
        hits = self.call("search_products", query="a")
        self.assertTrue(hits[1])  # one letter is too short to search
        self.assertFalse(self.call("search_products", query="a b")[1])  # two short words are a query, not an error
        self.assertEqual(
            self.call("search_products", query="Acme Docs")[0]["results"][0],
            {"id": "acme", "name": "Acme Docs", "category": "docs", "researched": True},
        )

    def test_a_blank_query_is_refused_rather_than_matching_everything(self):
        text, failed = self.call("search_products", query="   ")
        self.assertTrue(failed)
        self.assertIn("Invalid arguments", text)

    def test_a_product_is_found_by_its_id_in_any_case(self):
        for asked in ("acme", "ACME", " Acme"):
            product = self.call("get_product", id=asked.strip())[0]
            self.assertEqual((product["id"], product["known"], product["facts"]), ("acme", True, 1))
        self.assertEqual(
            self.call("get_product", id="beta")[0]["note"],
            "Not observed: no fact from this product's own pages is published.",
        )

    def test_an_unknown_product_reads_the_same_from_every_tool(self):
        self.assertEqual(self.call("get_product", id="nope")[0], {"id": "nope", "known": False})
        self.assertEqual(self.call("get_evidence", id="nope")[0], {"id": "nope", "known": False})

    def test_evidence_carries_each_quote_with_its_page_and_dates(self):
        fact = self.call("get_evidence", id="acme")[0]["facts"][0]
        self.assertEqual((fact["quote"], fact["url"], fact["verified"]), (FACT["quote"], FACT["url"], "2026-11-02"))

    def test_changes_since_is_newest_first_and_bounded_by_date(self):
        rows = self.call("changes_since", since="2026-09-01")[0]
        self.assertEqual([r["id"] for r in rows["facts"]], ["acme", "gamma"])
        self.assertEqual(self.call("changes_since", since="2026-10-15")[0]["total"], 1)

    def test_a_stack_review_returns_one_entry_per_id(self):
        self.assertEqual(
            [r["known"] for r in self.call("review_stack", ids=["acme", "nope"])[0]["results"]], [True, False]
        )

    def test_bad_arguments_are_tool_errors_the_caller_can_correct(self):
        for args in ({"id": "../etc"}, {}, {"id": "acme", "extra": 1}):
            text, failed = self.call("get_product", **args)
            self.assertTrue(failed, args)
            self.assertIn("Invalid arguments", text)

    def test_protocol_errors_use_json_rpc_codes(self):
        self.assertEqual(
            self.rpc("tools/call", {"name": "nope"})["error"], {"code": -32602, "message": "unknown tool: nope"}
        )
        self.assertEqual(self.rpc("resources/list")["error"]["code"], -32601)
        self.assertEqual(self.server.handle([])["error"]["code"], -32600)
        self.assertIsNone(self.server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_without_pulled_data_every_tool_says_how_to_get_it(self):
        res = McpServer(self.root / "missing").call_tool("search_products", {"query": "acme"})
        self.assertTrue(res["isError"])
        self.assertIn("run ./pull.sh", res["content"][0]["text"])


class Stdio(unittest.TestCase):
    def test_the_server_answers_line_by_line_and_survives_bad_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_site(Path(tmp))
            lines = ["not json", json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping"}), ""]
            out = subprocess.run(
                [sys.executable, "-m", "airstack.mcp_server", tmp],
                input="\n".join(lines),
                capture_output=True,
                text=True,
                cwd=ROOT,
                check=True,
            ).stdout.splitlines()
        self.assertEqual([json.loads(line).get("error", {}).get("code") for line in out], [-32700, None])
        self.assertEqual(json.loads(out[1]), {"jsonrpc": "2.0", "id": 7, "result": {}})


if __name__ == "__main__":
    unittest.main()
