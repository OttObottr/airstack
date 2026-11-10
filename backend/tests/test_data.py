"""The published method and the public builders: the quote check, the feed and open-data release, the MCP list and the stats card."""
import build_feed as bfeed
import gzip
import json
import pytest
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from conftest import ROOT
from airstack import paths
from airstack.mcp_server import DESCRIPTIONS
from decimal import Decimal
from airstack.quotes import check, found, has_money, norm, page_text, parse_price


PAGE = "<html><body><h1>Acme</h1><p>Acme integrates with Alpha Call and Beta Call.</p>" \
       "<p>Supports 30+ languages. Available on iPhone and Android.</p><p>SOC 2 Type II and HIPAA compliant.</p>" + "<p>filler text</p>" * 80 + "</body></html>"

def test_values_are_checked_against_the_page_not_trusted():
    text = norm(page_text(PAGE))
    assert check({"metric": "x.devices", "value_json": '["iPhone", "Android", "Windows"]', "quote": "Available on iPhone and Android.", "source_ts": ""}, text)[2] == ["Android", "iPhone"]
    assert not check({"metric": "x.price", "value_json": "1", "quote": "Acme", "source_ts": ""}, text)[0]          # outside the vocabulary
    assert not check({"metric": "x.store_users", "value_json": "true", "quote": "Supports 30+ languages.", "source_ts": ""}, text)[0]

def test_shapes_are_coerced_by_code_only_when_the_quote_still_holds():
    text = norm(page_text("<p>Rated 4.8 / 5</p><p>Cross-App Productivity: 100+ apps.</p>" + "<p>pad</p>" * 50))
    assert check({"metric": "x.store_rating", "value_json": '"4.8 / 5"', "quote": "Rated 4.8 / 5", "source_ts": ""}, text)[2] == {"rating": 4.8, "count": ""}
    assert check({"metric": "x.store_rating", "value_json": "4.9", "quote": "Rated 4.8 / 5", "source_ts": ""}, text)[0] is False
    assert check({"metric": "x.integrations", "value_json": "100", "quote": "Cross-App Productivity: 100+ apps.", "source_ts": ""}, text, "integrations")[2] == ("x.integrations_count", 100)

def test_a_ratings_count_is_not_accepted_as_a_user_count():
    text = norm(page_text("<p>9 Ratings</p><p>Extension Communication 500,000 users</p>" + "<p>pad</p>" * 60))
    assert check({"metric": "x.store_users", "value_json": "9", "quote": "9 Ratings", "source_ts": ""}, text) == (False, "the quote does not say users", None)
    assert check({"metric": "x.store_users", "value_json": "500000", "quote": "Extension Communication 500,000 users", "source_ts": ""}, text)[0] is True

def test_a_wrong_shape_is_repaired_in_code_but_the_page_still_decides():
    text = norm(page_text("<p>SOC 2 Type II and HIPAA compliant.</p><p>Trusted by 11M + developers.</p><p>MIT license</p><p>Runs locally and self-hosted.</p>" + "<p>pad</p>" * 60))
    ok = lambda m, v, q: check({"metric": m, "value_json": v, "quote": q, "source_ts": ""}, text)
    assert ok("x.compliance", '"HIPAA"', "SOC 2 Type II and HIPAA compliant.")[2] == ["HIPAA"]       # a bare string becomes a one-item list
    assert ok("x.compliance", "SOC 2 Type II, HIPAA", "SOC 2 Type II and HIPAA compliant.")[2] == ["HIPAA", "SOC 2 Type II"]   # an unquoted "A, B": split, each checked
    assert ok("x.compliance", '"ISO 27001"', "SOC 2 Type II and HIPAA compliant.")[0] is False       # a name that is not in the quote is dropped
    assert ok("x.compliance", "true", "SOC 2 Type II and HIPAA compliant.")[0] is False               # no names to check: still rejected
    assert ok("x.customers_claimed", "11000000", "Trusted by 11M + developers.")[2] == "Trusted by 11M + developers."   # the value is the page's own words
    assert ok("x.license", "MIT", "MIT license")[2] == "MIT license"
    assert ok("x.deployment", "self-hosted", "Runs locally and self-hosted.")[2] == ["self-hosted"]
    assert ok("x.open_source", "true", "MIT license")[2] is True
    assert ok("x.license", "MIT", "Apache 2.0 license")[0] is False                                   # a quote that is not on the page never passes


def admitted(metric, value, quote):
    return check({"metric": metric, "value_json": json.dumps(value), "quote": quote}, norm(quote))[0]

FREE_PLANS = ["Start free on cloud", "Free to get started. Flexibility at scale.", "Everything in Free, plus:", "Free: 1,000 credits every month, 10 a minute, 2 at a time.",
              "Start for free No credit card required", "Free, no credit card required", "Forever $0 /mo", "Starter\nFor everyone\n$0 / month", "Automatic mode is free; no card required"]

NOT_FREE_PLANS = ["You can create an account and start immediately with no credit card required.",
                  "Start with 5,000 free credits.", "Free $200 credit then pay-as-you-go", "Start free trial No credit card required",
                  "Start free with trial credits — no card required.", "Free credits $ 1 once per person.", "Start for free with $30 of credits, and pay only for what your agents run.",
                  "Pay as you go\n$0\nPay per token for every cloud model.", "Limited features included with the Basic plan."]

@pytest.mark.parametrize("quote", FREE_PLANS)
def test_a_free_plan_is_admitted_when_the_quote_says_free_or_zero_a_month(quote):
    assert admitted("x.free_plan", True, quote)

@pytest.mark.parametrize("quote", NOT_FREE_PLANS)
def test_a_trial_one_time_credits_or_pay_as_you_go_is_not_a_free_plan(quote):
    assert not admitted("x.free_plan", True, quote)

def test_a_ratings_count_is_not_a_user_count_and_a_code_fragment_is_not_a_description():
    assert not admitted("x.store_users", 9, "9 Ratings") and admitted("x.store_users", 1000, "1,000 users")
    assert not admitted("x.what_it_does", "x", 'await client.speech.convert( "voice-0001" , {')
    assert admitted("x.what_it_does", "x", "This is an AI-powered editor that goes beyond simple autocomplete.") and admitted("x.what_it_does", "x", "Run language models locally")


@pytest.mark.parametrize("quote, held", [("SOC 2 Type II certified.", True), ("Acme is a PCI DSS Level 1 Service Provider.", True),
    ("SOC 2 Type II is in progress.", False), ("We are working towards ISO 27001.", False), ("Acme aims to achieve SOC 2.", False),
    ("ISO 27001 certification is planned.", False), ("HIPAA-ready.", False), ("Acme supports the requirements of GDPR.", False),
    ("We store your data in ISO 27001 compliant data centers.", False), ("A PCI-DSS Level 1 compliant payment processor.", False),
    ("Not SOC 2 compliant yet.", False), ("Meet requirements like GDPR, HIPAA and SOC 2.", False), ("SOC 2 Type II", False), ("GDPR\nHIPAA", False),
    ("Acme isn't HIPAA compliant.", False), ("Stay compliant with GDPR.", False), ("Acme is ISO 27001 certified.", True), ("HIPAA\nCOMPLIANT", True)])
def test_a_certification_counts_only_when_the_quote_says_it_is_held(quote, held):
    assert admitted("x.compliance", ["SOC 2 Type II", "ISO 27001", "PCI DSS", "PCI-DSS", "HIPAA", "GDPR", "SOC 2"], quote) is held

@pytest.mark.parametrize("metric, value, quote, ok", [
    ("x.founded_year", 1200, "Trusted by 120,000 teams", False), ("x.integrations_count", 10, "Connect 100+ apps", False),
    ("x.integrations_count", 100, "Connect 100+ apps", True), ("x.store_users", 120000, "120,000 users", True), ("x.store_users", 120, "120,000 users", False),
    ("x.founded_year", 2012, "Founded in 2012.", True), ("x.sdk_languages", ["Go", "R", "C"], "Sign in with Google", False),
    ("x.sdk_languages", ["C"], "SDKs for C++ and C#", False), ("x.sdk_languages", ["Go", "C++"], "SDKs for Go, C++ and Rust", True),
    ("x.store_rating", 4.5, "Rated 4.5 out of 5", True), ("x.store_rating", 5, "Rated 4.5 out of 5", True), ("x.store_rating", 4.8, "Rated 4.85", False)])
def test_numbers_are_whole_tokens_and_names_are_whole_words_inside_the_quote(metric, value, quote, ok):
    assert admitted(metric, value, quote) is ok

def test_a_short_quote_matches_whole_tokens_only():
    text = norm("Products\nProfessional plan\nSlackware")
    for q in ("Pro", "Slack", "Free"):
        assert check({"metric": "x.plan_names", "value_json": json.dumps([q]), "quote": q}, text)[1] == "quote not found on the page"
    assert found(norm("Professional plan"), text) and not found(norm("Pro"), text)

def test_page_text_reads_only_visible_text_and_joins_inline_elements():
    t = page_text('<head><title>Acme</title></head><p>Pro <b>$</b>9<sup>.99</sup> / month</p><!-- SOC 2 certified --><div hidden>HIPAA<p>secret</div>'
                  '<span aria-hidden="true">x</span><template>t</template><img alt="SOC 2"><ul><li>A</li><li>B</li></ul><table><tr><td>a</td><td>b</td></tr></table>')
    assert t.splitlines() == ["Acme", "Pro $9.99 / month", "A", "B", "a b"]

def test_norm_folds_compatibility_forms_format_characters_dashes_and_quotes():
    assert norm("Ｐｒｏ\u00adfessional\u200b “Plan” — it’s ＳＯＣ２") == norm('professional "plan" - it\'s soc 2')
    assert found(norm("セキュリティセット"), norm("セキュリティセットに申し込む")) and found(norm("Acme"), norm("we use Acme.Then"))   # words without spaces

@pytest.mark.parametrize("text, lang, amount, currency, ambiguous", [
    ("USD 9", None, "9", "USD", False), ("9 €", None, "9", "EUR", False), ("₹499", None, "499", "INR", False), ("CHF 32", None, "32", "CHF", False),
    ("R$ 49,90", None, "49.90", "BRL", False), ("CA$12", None, "12", "CAD", False), ("$1,200.50 / year", None, "1200.50", "USD", False),
    ("1.200,50 €", None, "1200.50", "EUR", False), ("$0.015 per minute", None, "0.015", "USD", False), ("$1,200", None, None, "USD", True),
    ("$1,200", "en-US", "1200", "USD", False), ("1.200 €", "de", "1200", "EUR", False), ("12,000,000 ₩", None, "12000000", "KRW", False)])
def test_one_price_parser_reads_symbols_codes_and_separators_or_says_ambiguous(text, lang, amount, currency, ambiguous):
    p = parse_price(text, lang)
    assert (p["amount"], p["currency"], p["ambiguous"]) == (amount and Decimal(amount), currency, ambiguous)

def test_json_ld_is_not_page_text_and_money_is_found_in_any_currency():
    ld = '<script type="application/ld+json">{"@type": "Product", "name": "Pro", "offers": {"@type": "Offer", "price": "9.99", "priceCurrency": "eur"}}</script>'
    assert page_text(ld) == ""
    assert has_money("Raised €5M") and has_money("from 49 CHF") and has_money("₹499") and not has_money("Version 2.0, 3 seats") and not has_money("Try 30 days") and not has_money("PHP2Shell, PHP 8.4") and parse_price("Free") is None

def test_an_integration_counts_only_from_an_integrations_page_or_a_quote_that_presents_one():
    integration = lambda quote, kind=None: check({"metric": "x.integrations", "value_json": '["Beta"]', "quote": quote}, norm(quote), kind)[0]
    assert integration("Connect Beta in one click.") and integration("Beta", "integrations")
    assert not integration("Beta") and not integration("We use Beta to send email.") and not integration("Beta is our payment processor.", "integrations")


A = "{http://www.w3.org/2005/Atom}"

RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

OK = "https://vendor.test/changelog/v2"

def news(*items, read="2026-11-05"):
    return {"source": {"read": read, "window_days": 30}, "items": [{"id": "acme", "name": "Acme", "kind": "changelog", **i} for i in items]}

def events(*evs):
    return {"source": {"built_for": "2026-11-05"}, "events": [{"id": "acme", "name": "Acme", "precision": "day", **e} for e in evs]}

def release():
    return sorted(paths.OPEN_DATA.glob("airstack-*.jsonl.gz"))

def test_the_feed_is_well_formed_atom_and_every_entry_has_an_id_a_title_a_link_and_a_date():
    feed = ET.parse(paths.FEED).getroot()
    assert feed.tag == A + "feed"
    for t in ("id", "title", "updated", "author/" + A + "name"):
        assert (feed.findtext(A + t) or "").strip(), t
    assert any(ln.get("rel") == "self" and ln.get("href") == "https://airstack.bot/changes.atom" for ln in feed.findall(A + "link"))
    es = feed.findall(A + "entry")
    assert 0 < len(es) <= 200
    import build_pages
    slugs = {p["slug"] for p in (lambda a: build_pages.built(a, build_pages.own_prices(a, json.loads(paths.PRICING.read_text()))))(build_pages.products()).values()}
    ids, dates = [], []
    for e in es:
        ids.append(e.findtext(A + "id")); dates.append(e.findtext(A + "updated"))
        assert ids[-1].startswith("tag:airstack.bot,2026:") and (e.findtext(A + "title") or "").strip()
        assert RFC3339.match(dates[-1]) and datetime.fromisoformat(dates[-1])
        links = {ln.get("rel"): ln.get("href") for ln in e.findall(A + "link")}
        assert links["alternate"].startswith(("https://", "http://"))
        if "related" in links:
            m = re.fullmatch(r"https://airstack\.bot/p/([a-z0-9-]+)/", links["related"])
            assert m and m.group(1) in slugs, links["related"]
    assert len(set(ids)) == len(ids) and dates == sorted(dates, reverse=True)
    assert feed.findtext(A + "updated") == dates[0]

def test_only_observed_changes_in_the_window_appear_newest_first_without_duplicates():
    n = news({"title": "Release <2> & notes\x0b", "url": OK, "date": "2026-11-04T10:00:00+00:00"}, {"title": "Too old", "url": "https://vendor.test/old", "date": "2026-10-01T00:00:00Z"},
             {"title": "After the read", "url": "https://vendor.test/next", "date": "2026-11-06T00:00:00Z"})
    ev = events({"at": "2026-11-04", "status": "observed", "kind": "changelog", "title": "Release <2> & notes", "url": OK},   # the same change, from news.json
                {"at": "2026-11-02", "status": "observed", "kind": "end of life", "title": "Acme 1: end of life", "url": "https://endoflife.date/acme"},
                {"at": "2026-11-02", "status": "observed", "kind": "end of life", "title": "Acme 2: end of life", "url": "https://endoflife.date/acme"},
                {"at": "2026-11-03", "status": "scheduled", "kind": "end of life", "title": "Acme 3: end of life", "url": "https://endoflife.date/acme"},   # a date, not a record
                {"at": "2026-11-03", "status": "recheck", "kind": "answer recheck", "title": "Re-check by this day", "url": "https://airstack.bot/#/record"},
                {"at": "2026-11-21", "until": "2026-11-30", "precision": "window", "status": "expected", "kind": "release", "title": "Next release expected", "url": None})
    got = bfeed.changes(n, ev, {"acme": "acme"})
    assert [x["title"] for x in got] == ["Release <2> & notes", "Acme 1: end of life", "Acme 2: end of life"]
    assert got[0]["id"] == "tag:airstack.bot,2026:" + OK and len({x["id"] for x in got}) == 3   # one support page, two cycles, two ids
    feed = ET.fromstring(bfeed.atom(got, "2026-11-05", 30))                      # escaped, and the control character is gone
    assert feed.findtext(f"{A}entry/{A}title") == "Release <2> & notes" and feed.findtext(A + "updated") == "2026-11-04T10:00:00Z"
    assert feed.find(f"{A}entry/{A}link[@rel='related']").get("href") == "https://airstack.bot/p/acme/"
    assert bfeed.changes(n, ev, {})[0]["page"] is None  # no page, no related link
    assert bfeed.atom(got, "2026-11-05", 30) == bfeed.atom(bfeed.changes(n, ev, {"acme": "acme"}), "2026-11-05", 30)
    many = news(*({"title": f"r{i}", "url": f"https://vendor.test/r{i}", "date": f"2026-11-0{1 + i % 4}T{i % 24:02d}:00:00Z"} for i in range(250)))
    capped = bfeed.changes(many, events(), {})
    assert len(capped) == paths.config("pages")["limits"]["feed_entries"] and [x["updated"] for x in capped] == sorted((x["updated"] for x in capped), reverse=True)

def test_the_release_holds_only_published_facts_and_no_stored_page_text():
    chain = json.loads(paths.CHAIN_DATA.read_text())
    shown = {(pid, f["metric"], f["url"], f["quote"], json.dumps(f["value"], sort_keys=True)) for pid, e in chain["entities"].items() for f in e["facts"]}
    files = release()
    assert files
    newest = gzip.decompress(files[-1].read_bytes()).decode().splitlines()
    assert newest
    for f in files:
        for line in gzip.decompress(f.read_bytes()).decode().splitlines():
            r = json.loads(line)
            assert tuple(sorted(r)) == tuple(sorted(bfeed.OPEN_FIELDS))
            assert len(r["quote"].split()) <= 25 and r["licence"] in {bfeed.LICENCE, bfeed.LICENCE_WIKIMEDIA}
            if f == files[-1]:
                assert (r["id"], r["metric"], r["url"], r["quote"], json.dumps(r["value"], sort_keys=True)) in shown, line[:200]
    src = (ROOT / "backend" / "tools" / "build_feed.py").read_text()
    assert "sqlite3" not in src

def test_the_feed_and_release_are_rebuilt_from_the_published_files():
    out = bfeed.build()
    assert {"changes.atom", "open-data/README.md"} <= set(out) and any(k.endswith(".jsonl.gz") for k in out)
    stale = [k for k, v in out.items() if not (paths.SITE / k).exists() or not bfeed.same(k, v, (paths.SITE / k).read_bytes())]
    assert not stale, f"stale: {stale}; run backend/tools/build_feed.py"


def test_the_agents_page_lists_the_mcp_tools_from_one_source():
    site = paths.read_js(paths.SITE_DATA)
    expected = sorted(DESCRIPTIONS)
    assert site["execution"]["mcp"]["tools"] == expected
    html = (paths.ROOT / "web" / "index.html").read_text()
    assert 'id="agTools"' in html and not any(f"Tools: {name}" in html for name in expected)


def test_the_stats_card_is_what_the_data_builds():
    before = paths.STATS_SVG.read_text()
    subprocess.run([sys.executable, str(ROOT / "backend/tools/build_stats.py")], check=True, capture_output=True)
    svg = paths.STATS_SVG.read_text()
    assert svg == before
    t = paths.SITE_DATA.read_text(); site = json.loads(t[t.index("{"):t.rindex("}") + 1])
    assert f'>{len(site["index"]) + site["dir"]["products"]:,}</text>' in svg and f'>{site["dir"]["orgs"]:,}</text>' in svg
    assert "$" not in svg and "<script" not in svg
    assert "prefers-reduced-motion:reduce" in svg


TRICKY = ["Fast, simple & secure", "Real-time sync — no setup", "Prix: 10 € / mois, TVA incluse", "日本語のドキュメント",
          "Use it from the CLI, the Web dashboard or the API, on macOS, Windows and Linux, wherever you work.",
          "Team\n$20 per user", "a+b = c? 100% (beta)! it's *new*", "  spaced\tout   words  ", "Ünïcödé, “curly” quotes – dash"]

def directive(link):
    return link.split("#:~:text=", 1)[1]

@pytest.mark.parametrize("quote", TRICKY)
def test_a_text_fragment_encodes_every_syntax_character_and_decodes_back_to_the_quote(quote):
    from urllib.parse import unquote
    from airstack.evidence import text_fragment
    d = directive(text_fragment("https://acme.example/page", quote))
    terms = d.split(",")
    assert 1 <= len(terms) <= 2 and all(re.fullmatch(r"(?:[A-Za-z0-9_.~]|%[0-9A-F]{2})+", t) for t in terms)   # '-', ',', '&' and spaces never raw
    words = " ".join(quote.split())
    if len(terms) == 1:
        assert unquote(terms[0]) == words
    else:
        assert words.startswith(unquote(terms[0])) and words.endswith(unquote(terms[1]))

def test_a_text_fragment_joins_an_existing_fragment_and_skips_an_empty_quote():
    from airstack.evidence import text_fragment
    assert text_fragment("https://acme.example/docs#plans", "Free plan") == "https://acme.example/docs#plans:~:text=Free%20plan"
    assert text_fragment("https://acme.example/", " \n ") == "https://acme.example/"
    assert directive(text_fragment("https://acme.example/", "Team\n$20")) == "Team,%2420"

def test_the_browser_builds_the_same_links_as_the_static_pages():
    from airstack.evidence import report_url, text_fragment
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = (ROOT / "web" / "src" / "lib" / "format.js").as_uri()
    script = (f"import {{ textFragment, reportUrl }} from '{src}'; const q = JSON.parse(process.argv[1]);"
              "console.log(JSON.stringify(q.map(x => [textFragment('https://acme.example/p', x), reportUrl('Acme (beta)', 'Plans', 'https://acme.example/p', x)])));")
    out = json.loads(subprocess.run([node, "--input-type=module", "-e", script, json.dumps(TRICKY)], check=True, capture_output=True, text=True).stdout)
    assert out == [[text_fragment("https://acme.example/p", q), report_url("Acme (beta)", "Plans", "https://acme.example/p", q)] for q in TRICKY]

def test_no_high_tier_claim_reaches_a_published_file_or_page():
    from airstack.evidence import shown
    policy = json.loads(paths.CHAIN_DATA.read_text())["policy"]
    high = policy["tiers"]["high"]
    assert high and not any(shown(policy, m) for m in high)
    assert not {k for p in json.loads(paths.PROFILES.read_text()).values() for k in p} & set(high)
    assert not {f["metric"] for e in json.loads(paths.CHAIN_DATA.read_text())["entities"].values() for f in e["facts"]} & set(high)
    for f in paths.OPEN_DATA.glob("*.jsonl.gz"):
        assert not {json.loads(line)["metric"] for line in gzip.decompress(f.read_bytes()).decode().splitlines()} & set(high)
    labels = dict(paths.config("pages")["labels"])
    site = paths.read_js(paths.SITE_DATA)
    assert not {k for k, _ in site["labels"]} & set(high) and site["policy"] == policy
    for page in [*(ROOT / "p").glob("*/index.html"), *(ROOT / "compare").glob("*/index.html"), *(ROOT / "c").glob("*/index.html"), ROOT / "insights" / "index.html"]:
        h = page.read_text()
        text = re.sub(r"<[^>]+>", " ", re.sub(r"<q>.*?</q>|<a [^>]*>", " ", h, flags=re.S))     # AirStack's own words, not the vendors' quotes
        assert not any(f"<th>{labels[m]}</th>" in h for m in high if m in labels), page
        assert not re.search(r"\b(SOC 2|ISO 27001|HIPAA)\b|\bStarting at\b|\bcheapest\b|\b(BUILD|BUY|KEEP|RETIRE)\b", text), page

def test_every_quoted_fact_on_a_product_page_carries_its_checks():
    if not (ROOT / "p" / "gamma-deploy" / "index.html").exists():
        pytest.skip("the synthetic fixture's product")
    page = (ROOT / "p" / "gamma-deploy" / "index.html").read_text()
    facts = page.split("<table>")[-1].split("</table>")[0]
    assert facts.count(" says: <q>") == facts.count(":~:text=") == facts.count("Report a problem") > 0
    assert "Archived copy" in facts and "first read" in facts
    assert "github.com/OttObottr/airstack/issues/new?title=" in facts
