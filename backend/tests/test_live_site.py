# spec: AS-066 AS-202
"""Checks the REAL deployment. Opt in with AIRSTACK_NETWORK_TESTS=1 (the daily CI job does)."""
import json, os, re, subprocess, urllib.request, urllib.error
import pytest
from airstack import paths
pytestmark = [pytest.mark.network, pytest.mark.skipif(os.environ.get("AIRSTACK_NETWORK_TESTS") != "1", reason="set AIRSTACK_NETWORK_TESTS=1")]
SITE = os.environ.get("AIRSTACK_SITE", "https://airstack.bot/")

def get(path):
    req = urllib.request.Request(SITE + path, headers={"User-Agent": "airstack-live-check"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""

def test_airstack_bot_serves_the_site_over_https():
    status, body = get("")
    assert status == 200 and "<title>AirStack" in body

def test_secrets_config_and_backend_code_are_never_served():
    for path in (".env", ".env.example", "wrangler.jsonc", "deploy.sh", "backend/airstack/config.py", ".git/config", "archive/hardware-draft.html",
                 "data/airstack-market.db", "data/ab-runs.json"):
        assert get(path)[0] == 404, path

def test_the_domain_is_on_cloudflare():
    """Ask the .bot registry itself (resolver caches may hold the old delegation for its 48 h TTL)."""
    tld = subprocess.run(["dig", "+short", "NS", "bot."], capture_output=True, text=True).stdout.split()[0]
    out = subprocess.run(["dig", "+norec", "NS", "airstack.bot", "@" + tld, "+noall", "+authority", "+answer"], capture_output=True, text=True).stdout
    assert re.search(r"\b[\w-]+\.ns\.cloudflare\.com\.", out) and "porkbun" not in out

def test_cloudflare_does_not_inject_an_analytics_beacon():
    status, body = get("")
    assert status == 200 and "cloudflareinsights" not in body


def test_scripts_and_data_are_served_compressed():
    for path in ("site-data.js", "market-data.js", "chain-data.json"):
        req = urllib.request.Request(SITE + path, headers={"User-Agent": "airstack-live-check", "Accept-Encoding": "br, gzip"})
        with urllib.request.urlopen(req, timeout=20) as r:
            assert r.headers.get("Content-Encoding") in ("br", "gzip"), (path, "served raw")


def test_production_serves_the_build_in_this_checkout():
    """Production serves the exact build from this checkout."""
    import verify_deploy
    assert verify_deploy.differences(SITE) == []


def test_the_mcp_example_shown_on_the_page_is_local_and_matches_the_recorded_answer():
    """AS-136: the page documents local MCP and its example comes from the generated record."""
    ex = paths.read_js(paths.SITE_DATA)["execution"]["mcp"]
    assert ex["request"]["params"]["name"] == "assess" and "seat" not in json.dumps(ex["request"])
    assert ex["response"]["verdicts"][0]["action"] in ("KEEP", "RETIRE")
