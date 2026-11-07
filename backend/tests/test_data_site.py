# spec: AS-055 AS-130 AS-134 AS-237 AS-248 AS-250 AS-251 AS-254 AS-255 AS-258 AS-264 AS-265 AS-295 AS-298 AS-317 AS-350
from conftest import *
import build_brief as bbrief, build_community as c, build_demo_data, build_directory as directory, build_news as bn, build_pricing as bpricing, build_site_data as bsd, json, pathlib, pytest, re, subprocess, sys, urllib.parse
from airstack import paths
from check_catalog import BLOCKED, CATEGORIES, KINDS, owned, reg


def test_the_agents_page_lists_the_workers_canonical_tools_without_a_second_copy():
    site = paths.read_js(paths.SITE_DATA)
    from airstack.mcp_server import DESCRIPTIONS
    expected = sorted(DESCRIPTIONS)
    assert site["execution"]["mcp"]["tools"] == expected
    html = (paths.ROOT / "web" / "index.html").read_text()
    assert 'id="agTools"' in html and not any(f"Tools: {name}" in html for name in expected)


# --- brief: The daily brief: written by a model, published only if code finds every number in the facts each sentence cites. ---

F = {"d1": {"text": "387 tools are tracked: 12 developer and AI lanes and 16 business software categories."},
     "d2": {"tool": "vllm", "text": "vLLM (Local inference): 699,455 PyPI downloads in the last 7 days, +24.1% on the week before and +51.3% against its own 4-week level."},
     "d3": {"tool": "openhands", "text": "OpenHands (Coding agents): +107.0% on the week before, but -51.6% against its own 4-week level: a rebound, not growth."}}

def brief(*items, headline="What moved this week"):
    return {"headline": headline, "items": [{"text": t, "cites": c} for t, c in items]}

def test_a_brief_whose_numbers_all_come_from_the_facts_it_cites_is_publishable():
    ok = brief(("vLLM gained 24.1% on the week before, 51.3% above its own 4-week level.", ["d2"]),
               ("OpenHands rose 107.0% but is still 51.6% under its usual level: a rebound.", ["d3"]),
               ("AirStack tracks 387 tools in 16 business categories.", ["d1"]))
    assert bbrief.check(ok, F) == []

def test_a_number_from_nowhere_or_from_a_fact_it_did_not_cite_blocks_publication():
    assert bbrief.check(brief(("vLLM gained 30% this week.", ["d2"]), ("x", ["d1"]), ("y", ["d1"])), F) == ["item 1: 30 is not in the facts it cites"]
    assert bbrief.check(brief(("vLLM gained 107.0%.", ["d2"]), ("x", ["d1"]), ("y", ["d1"])), F) == ["item 1: 107.0 is not in the facts it cites"]   # true elsewhere, not where cited
    assert bbrief.check(brief(("x", ["d9"]), ("y", ["d1"]), ("z", ["d1"])), F) == ["item 1: cites unknown facts ['d9']"]
    assert bbrief.check(brief(("x", ["d1"]), ("y", ["d1"]), ("z", ["d1"]), headline="99 tools surged"), F) == ["headline: 99 is not in any fact"]

def test_money_and_banned_wording_block_publication():
    assert bbrief.check(brief(("vLLM costs $20 a seat.", ["d2"]), ("x", ["d1"]), ("y", ["d1"])), F) == ["item 1: 20 is not in the facts it cites", "item 1: banned wording"]
    assert bbrief.check(brief(("vLLM will keep growing.", ["d2"]), ("x", ["d1"]), ("y", ["d1"])), F) == ["item 1: banned wording"]

def test_each_number_must_carry_its_facts_unit_direction_and_subject():
    """AS-350: a number that is in the cited fact is not enough; it must mean what it means there."""
    one = lambda t, c="d2": bbrief.check(brief((t, [c])), F)
    assert one("vLLM had 699,455 GitHub stars in the last 7 days.") == ["item 1: 699455 does not name its unit"]
    assert one("vLLM rose 24.1 PyPI downloads.") == ["item 1: 24.1 does not name its unit"]                  # a percentage is not a count
    assert one("vLLM: 24.1 PyPI downloads.") == ["item 1: 24.1 does not name its unit or direction"]
    assert one("vLLM fell 24.1% on the week before.") == ["item 1: 24.1 does not name its direction"]        # the fact says +24.1%
    assert one("vLLM moved 24.1% on the week before.") == ["item 1: 24.1 does not name its direction"]       # no direction at all
    assert one("OpenHands is at -51.6% and rose 107.0% on the week before.", "d3") == []
    assert one("OpenHands is at 51.6% and rose 107.0%.", "d3") == ["item 1: 51.6 does not name its direction"]
    assert one("+387 tools are tracked.", "d1") == ["item 1: 387 does not name its direction"]               # a sign on a count invents a change
    assert one("vLLM fell to 699,455 PyPI downloads in the last 7 days.") == ["item 1: 699455 does not name its direction"]   # and so does a word
    assert one("OpenHands had 699,455 PyPI downloads.") == ["item 1: 699455 does not name its subject"]        # the fact is about vLLM
    assert bbrief.check(brief(headline="Downloads up 24.1% on the week before"), F) == ["headline: 24.1 does not name its subject"]
    assert bbrief.check(brief(headline="vLLM up 24.1% on the week before"), F) == []
    both = lambda t: bbrief.check(brief((t, ["d2", "d3"])), F)                                                  # each number is the tool's named last before it
    assert both("vLLM rose 24.1% on the week before while OpenHands rose 107.0%.") == []
    assert both("vLLM rose 107.0% on the week before while OpenHands rose 24.1%.") == ["item 1: 107.0 does not name its subject", "item 1: 24.1 does not name its subject"]
    assert bbrief.check(brief(headline="vLLM up 107.0% and OpenHands up 24.1%"), F) == ["headline: 107.0 does not name its subject", "headline: 24.1 does not name its subject"]

def test_a_sentence_that_breaks_the_contract_is_withheld_and_the_rest_is_published(tmp_path, monkeypatch):
    monkeypatch.setattr(bbrief, "OUT", tmp_path / "brief.json")
    B = {"date": "2026-11-04", "model": "m", "call_ref": "r", **brief(("vLLM gained 24.1% on the week before.", ["d2"]), ("vLLM fell 24.1% this week.", ["d2"]),
                                                                        ("387 tools are tracked.", ["d1"]), ("vLLM gained 31.7% this week.", ["d2"]))}
    assert bbrief.publish(B, F) == 0
    out = json.loads((tmp_path / "brief.json").read_text())
    assert [it["text"] for it in out["items"]] == ["vLLM gained 24.1% on the week before.", "387 tools are tracked."]
    assert out["withheld"] == [{"cites": ["d2"], "why": ["a number does not name its direction"]},            # why it was dropped, not its words
                               {"cites": ["d2"], "why": ["a number is not in the facts it cites"]}]
    assert "31.7" not in (tmp_path / "brief.json").read_text()                                                 # nor a number the model made up: the file ships in the page data
    assert bbrief.check(out, F) == []
    (tmp_path / "brief.json").unlink()
    assert bbrief.publish({**B, "headline": "99 tools surged"}, F) == 1 and not (tmp_path / "brief.json").exists()   # a bad headline cannot be dropped: nothing is published
    assert bbrief.publish({**B, "items": B["items"][1:2]}, F) == 1 and not (tmp_path / "brief.json").exists()       # nor a brief with no sentence left

@pytest.mark.private_data
def test_the_stored_brief_holds_to_the_contract_and_a_recheck_costs_nothing_and_changes_nothing(tmp_path, monkeypatch):
    stored = paths.BRIEF
    B = json.loads(stored.read_text())
    assert bbrief.check(B, B["facts"]) == []
    monkeypatch.setattr(bbrief, "OUT", tmp_path / "brief.json"); (tmp_path / "brief.json").write_bytes(stored.read_bytes())
    monkeypatch.setattr(bbrief, "facts", lambda: (_ for _ in ()).throw(AssertionError("a recheck reads only the stored brief")))
    assert bbrief.main(["--recheck"]) == 0 and (tmp_path / "brief.json").read_bytes() == stored.read_bytes()

def test_the_facts_label_a_rebound_as_a_rebound():
    rows = [f["text"] for f in bbrief.facts().values()]
    assert any("tools are tracked" in t for t in rows) and all("$" not in t for t in rows)
    assert all("a rebound, not growth" in t for t in rows if "against its own 4-week level" in t and ", but -" in t)


# --- community: Communities and public channels as Wikidata records them: rebuilt offline from saved responses, every count dated and on a platform, no personal data. ---

BODY = paths.COMMUNITY.read_text()

CD = json.loads(BODY)

EMAIL = re.compile(r"(?<![@\w.+-])[\w.+-]+@[\w-]+(\.[\w-]+)+")      # a fediverse handle (@user@server) is not an e-mail address

@pytest.mark.private_data
def test_the_published_file_is_rebuilt_byte_for_byte_from_the_saved_wikidata_responses(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "OUT", tmp_path / "community.json")
    c.build()
    assert (tmp_path / "community.json").read_bytes() == paths.COMMUNITY.read_bytes()
    assert CD["source"]["licence"] == "CC0" and CD["source"]["fetched_at"] and "not that none exists" in CD["source"]["note"]

@pytest.mark.private_data
def test_every_entity_is_a_product_or_maker_airstack_lists():
    d = json.loads(paths.DIRECTORY.read_text())
    catalog = {t["id"]: t for t in json.loads(paths.CATALOG.read_text())}
    records, devs = {}, {}
    for p in directory.raw_products():
        records.setdefault(p["id"], set()).add((directory.host(p["site"]), c.key(p["name"]))); devs.setdefault(p["id"], set()).update(p["devs"])
    for cid, (item, *makers) in CD["catalog"].items():                 # a catalog product is joined only where website and name both agree
        t = catalog[cid]
        assert (directory.host(t["homepage"]), c.key(t["name"])) in records[item] and set(makers) <= devs[item], cid
    listed = {p[0] for p in d["products"]} | set(d["orgs"]) | {i for v in CD["catalog"].values() for i in v}
    assert CD["entities"] and set(CD["entities"]) <= listed
    for qid, e in CD["entities"].items():
        assert re.fullmatch(r"Q\d+", qid) and (e.get("links") or e.get("people")), qid

def test_every_follower_count_names_its_platform_and_is_a_whole_number_with_its_date_as_precise_as_wikidata_states_it():
    platforms = set(c.FOLLOWED_ON.values())
    for qid, e in CD["entities"].items():
        seen = [f[0] for f in e.get("followers", [])]
        assert len(seen) == len(set(seen)), qid                       # the latest count per platform, once
        for platform, n, when in e.get("followers", []):
            assert platform in platforms and type(n) is int and n >= 0, qid
            assert when is None or re.fullmatch(r"\d{4}(-\d\d(-\d\d)?)?", when), qid

def test_a_person_is_named_by_their_own_wikidata_item_and_role_only():
    """People are published by name, role and Wikidata item: never their personal accounts (compliance sweep, P4). Links are ids, not addresses."""
    for qid, e in CD["entities"].items():
        for row in e.get("people", []):
            assert len(row) == 3, (qid, row)
            person, name, role = row
            assert re.fullmatch(r"Q\d+", person) and name and role in {"founder", "ceo", "director"}, qid
        assert set(e.get("links", {})) <= set(c.LINKS.values()) | {"discord_invite"}, qid
        for k, v in e.get("links", {}).items():
            assert v and not v.startswith(("http://", "https://")) or k == "blog", qid   # ids and handles; the page builds the address
            assert k != "mastodon" or re.fullmatch(r"@[^@\s]+@[^@\s]+", v), qid

def test_no_field_holds_an_email_address():
    assert not EMAIL.search(BODY)


# --- directory: The directory: every software product and company Wikidata records with a website, rebuilt offline from saved responses. ---

D = json.loads(paths.DIRECTORY.read_text())

@pytest.mark.private_data
def test_the_published_directory_is_rebuilt_byte_for_byte_from_the_saved_wikidata_responses(tmp_path, monkeypatch):
    monkeypatch.setattr(directory, "OUT", tmp_path / "directory.json")
    directory.build()
    assert (tmp_path / "directory.json").read_bytes() == paths.DIRECTORY.read_bytes()
    assert D["source"]["license"] == "CC0 1.0" and D["source"]["fetched_at"] and "not researched" in D["source"]["note"]

def test_a_listing_is_software_with_a_website_and_a_record_and_nothing_the_catalog_already_covers():
    known = json.loads(paths.UNIVERSE.read_text()) + json.loads(paths.CATALOG.read_text())
    hosts, names = {directory.host(t.get("homepage")) for t in known} - {""}, {t["name"].lower() for t in known}
    kinds = [o[5] for o in D["orgs"].values()]
    assert len(D["products"]) > 10000 and len(kinds) - kinds.count("person") > 4000 and set(kinds) == {"business", "organization", "person"}   # a person is a maker, never counted as a company
    for qid, name, _desc, site, t, makers, pages, _aliases in D["products"]:
        assert qid.startswith("Q") and site.startswith(("http://", "https://")) and pages >= 1, qid
        assert directory.host(site) not in hosts and name.lower() not in names, qid               # the catalog's researched entry is the one shown
        assert not directory.NOT_A_PAGE_NAME.match(name) and not directory.NOT_SOFTWARE_LABEL.search(D["types"][t][1]), qid
        assert all(m in D["orgs"] for m in makers), qid
    assert len({p[0] for p in D["products"]}) == len(D["products"])
    key = lambda n: __import__("re").sub(r"[^a-z0-9]", "", n.lower())
    assert len({key(p[1]) for p in D["products"]}) == len(D["products"])                   # one listing per name: Wikidata's duplicate records are folded
    addr = lambda u: (directory.host(u) + __import__("urllib.parse").parse.urlsplit(u).path).rstrip("/").lower()
    assert len({addr(p[3]) for p in D["products"]}) == len(D["products"])                  # and per website address
    assert not {key(p[1]) for p in D["products"]} & {key(t["name"]) for t in known}       # a namesake of a tracked product is not listed beside it

def test_a_headcount_out_of_line_with_the_organizations_documentation_or_kind_is_flagged_and_never_carried_as_a_number():
    """Implausible headcounts do not enter firmographic rankings."""
    assert directory.implausible("business", 846_554, 0) and directory.implausible("person", 12, 40)       # Fintech Band, no page; a person is not an employer
    for n, pages, kind in [(1_500_000, 124, "business"), (779_000, 51, "business"), (600_000, 31, "business"), (2_870_000, 60, "organization"),
                           (44_868, 1, "organization"), (4_302, 0, "business"), (846_554, None, "business")]:   # Amazon, Accenture, TCS, DoD, Munich's city, Avalara; unknown pages are not judged
        assert directory.implausible(kind, n, pages) is None, (n, pages)
    odd, O = D["implausible"], D["orgs"]
    assert set(odd) == {"Q86603987"} and "846" not in odd["Q86603987"]                     # the reason never repeats the number
    assert all(O[o][6] is None and O[o][7] is None for o in odd) and all(len(o) == 9 for o in O.values())   # the row keeps its shape: the web reads it by index
    assert all(O[q][6] and q not in odd for q in ("Q3884", "Q338825", "Q26989", "Q81230"))   # Amazon, Accenture, Infosys, Siemens keep theirs

def test_the_taxonomy_hangs_from_software_and_its_counts_add_up():
    T = D["types"]
    assert T[0][:2] == ["Q7397", "software"] and T[0][4] == len(D["products"])
    assert all(t[2] and all(0 <= p < len(T) for p in t[2]) for t in T[1:])                     # every type has a parent in the tree
    assert sum(t[3] for t in T) == len(D["products"])                                          # each product counted once, under its own type
    assert all(t[4] >= t[3] for t in T)


# --- category_guides: AirStack's own category guides: labelled editorial, one per category and lane the site shows, short, and free of numbers, prices and hype. ---

GUIDES = json.loads(paths.CATEGORY_GUIDES.read_text())

JS = paths.SITE_DATA.read_text()

SITE = json.loads(JS[JS.index("{"):JS.rindex("}") + 1])

TEXT = {"what": 140, "watch_for": 140}

LISTS = {"why": (2, 4, 90), "jobs": (3, 5, 60), "who": (3, 6, 60), "bundled_by": (0, 4, 40)}

HYPE = re.compile(r"\b(revolutionar|seamless|cutting-edge|unlock|leverag|killer|game-chang|supercharg|effortless|best-in-class|world-class)", re.I)

VERDICT = re.compile(r"\b(BUILD|BUY|KEEP|RETIRE)\b")   # the engine's labels, never editorial

SCREEN = re.compile(r"\b(seats?|verdicts?|lapsed|tokens?)\b", re.I)   # plain words on screen, as on the card faces

def strings(g, prose_only=False):
    out = [g["what"], g["watch_for"], *g["why"], *g["jobs"], *g["who"]]
    return out if prose_only else out + g["bundled_by"]

def test_the_file_is_labelled_editorial():
    s = GUIDES["source"]
    assert s["kind"] == "editorial" and s["name"] == "AirStack category guides" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["written"])
    assert "Not a vendor claim and not a measurement" in s["note"]

def test_every_category_and_lane_on_the_site_has_a_guide_and_nothing_else():
    ids = {c["id"] for c in SITE["cats"]} | {l["id"] for l in SITE["lanes"]}
    assert len(ids) >= 36
    assert set(GUIDES["categories"]) == ids, (ids ^ set(GUIDES["categories"]))

def test_every_field_is_present_and_within_its_limit():
    for cid, g in GUIDES["categories"].items():
        assert set(g) == set(TEXT) | set(LISTS), cid
        for k, n in TEXT.items():
            assert isinstance(g[k], str) and 0 < len(g[k]) <= n, (cid, k, len(g[k]))
        for k, (lo, hi, n) in LISTS.items():
            assert lo <= len(g[k]) <= hi, (cid, k, len(g[k]))
            assert all(isinstance(t, str) and 0 < len(t) <= n for t in g[k]), (cid, k)
            assert len(set(g[k])) == len(g[k]), (cid, k)

def test_no_numbers_prices_hype_or_verdict_words():
    for cid, g in GUIDES["categories"].items():
        for t in strings(g):
            assert "$" not in t and not re.search(r"\d\s*%", t), (cid, t)
            assert not HYPE.search(t) and not VERDICT.search(t) and not SCREEN.search(t), (cid, t)
        for t in strings(g, prose_only=True):   # a platform name may carry a digit; prose may not: no unsourced figures
            assert not re.search(r"\d", t), (cid, t)


# --- demo_data ---

@pytest.mark.private_data
def test_the_demo_data_is_complete_and_never_claims_a_real_model_call(tmp_path):
    ex = build_demo_data.main(out=tmp_path)
    seats = {v["context"]: v for v in ex["verdicts"] if v["status"] == "CURRENT"}
    assert seats["seat:A"]["action"] == "RETIRE" and seats["seat:B"]["action"] == "KEEP"
    assert all(c["model"] == "fixture (no model call)" for c in ex["calls"]) and ex["calls"]
    assert all(f["url"].startswith("https://") and f["observed_at"] for f in ex["facts"])
    assert not [f for f in ex["facts"] if "example.invalid" in f["url"]] and ex["about"]["facts"] == "all real and sourced"
    a = next(v for v in ex["verdicts"] if v["context"] == "seat:A" and v["status"] == "CURRENT")
    ed = [r for r in a["requirements"] if r["id"] == "edition"][0]                     # the plan is a real predicate...
    assert ed["entitlement"] == "workspace:business_standard" and ed["entitlement"] in a["entitlements"]   # ...AND the seat must hold it
    assert all(v["visibility"] == "public" for v in ex["verdicts"])                    # only explicit public examples in the public DB
    assert a["judge_output"]["action"] == "RETIRE" and a["judge_output"]["citations"]
    assert ex["watches"] and {e["event"] for e in ex["verdict_events"]} == {"PUBLISHED", "LAPSED", "SUPERSEDED"}
    assert all("Available on iOS" not in c["request_json"] for c in ex["calls"])                     # private seat context redacted
    saved = json.loads(paths.DEMO_EXPORT.read_text())
    sourced = lambda e: [(f["entity_id"], f["metric"], f["url"]) for f in e["facts"] if not f["metric"].startswith("counter.")]
    assert sourced(saved) == sourced(ex)                                                # same sourced facts; live search may add counter-evidence rows

def test_a_database_holding_paid_calls_is_never_rebuilt_by_accident(tmp_path):
    """Paid Muse results are kept and reused. A fixture build (or a second live build) must refuse to delete them."""
    import pytest, sqlite3
    build_demo_data.main(out=tmp_path)                                                  # a fixture database: rebuilding it is fine
    build_demo_data.main(out=tmp_path)
    with sqlite3.connect(tmp_path / "airstack-demo.db") as c:                           # now it holds one paid call
        c.execute("UPDATE calls SET model = 'muse-spark-1.3' WHERE id = (SELECT min(id) FROM calls)")
    before = (tmp_path / "airstack-demo.db").read_bytes()
    with pytest.raises(build_demo_data.PaidDataProtected):
        build_demo_data.main(out=tmp_path)
    assert (tmp_path / "airstack-demo.db").read_bytes() == before                       # untouched


# --- insights: Market insights place a product only on measured inputs, name every denominator, and show only sourced list prices. ---

I = lambda: json.loads(paths.INSIGHTS.read_text())

def test_every_researched_product_is_placed_on_measured_inputs_or_counted_as_unplaced():
    d, P = I(), json.loads(paths.PROFILES.read_text())
    pts = d["map"]["points"]
    assert len(pts) + d["map"]["unplaced"] == len(P)
    assert all(p[3] > 0 and p[4] in (0, 1, 2) and p[0] in P for p in pts)
    assert all(p[4] != 2 or "what_it_does" in P[p[0]] for p in pts)          # "AI in its one-liner" needs the one-liner

def test_category_shares_have_their_denominator_and_the_median_price_is_a_quoted_list_price():
    d, Q = I(), json.loads(paths.PRICING.read_text())
    for c in d["categories"].values():
        assert 0 < c["researched"] <= c["listed"]
        assert all(0 <= c[k] <= c["researched"] for k in ("free_plan", "security_claim", "open_source", "ai_one_liner", "list_price"))
        m = c["median_seat"]
        if m:
            q = Q[m["id"]]
            assert m["url"] == q["url"] and any(p["plan"] == m["plan"] and p["price"] == m["price"] for p in q["plans"])

def test_the_ai_classifier_finds_ai_where_products_are_sold_as_ai():
    """A guard against a broken classifier, not a target share. Products cataloged as AI assistants, AI coding tools or creative AI, and
    the developer lanes built on models, sell AI by definition; if fewer than 75% of the researched ones show AI evidence on their own pages,
    the pattern has stopped matching (as when it once missed "coding agent" and "Claude SDK"). Below the threshold, fix the classifier,
    never the threshold."""
    import build_insights as bi
    P = json.loads(paths.PROFILES.read_text())
    cat = {c["id"]: c["category"] for c in json.loads(paths.CATALOG.read_text())}
    t = paths.SITE_DATA.read_text(); site = json.loads(t[t.index("{"):t.rindex("}") + 1]); lane = {r[0]: r[2] for r in site["index"]}
    AIC = {"ai-assistants", "ai-coding", "creative-ai", "coding-agents", "llm-sdks-and-routers", "agent-frameworks", "llm-evals", "llm-observability", "local-inference", "ai-app-builders"}
    roles = [bi.ai_role(p) for pid, p in P.items() if (cat.get(pid) or lane.get(pid)) in AIC and bi.ai_role(p) is not None]
    assert len(roles) >= 40 and sum(1 for r in roles if r >= 1) / len(roles) >= 0.75, (len(roles), sum(1 for r in roles if r >= 1))


# --- news: The news is each vendor's own announcement, a GitHub release, or an HN story linking to the product's own site: nothing else. ---

def test_every_item_links_to_its_products_own_site_or_its_repository_and_no_build_tags():
    cat = {p["id"]: p for p in json.loads(paths.CATALOG.read_text())}
    items = json.loads(paths.NEWS.read_text())["items"]
    assert items and {i["kind"] for i in items} <= {"changelog", "blog", "release", "hacker news"}
    for i in items:
        if i["kind"] in ("changelog", "blog", "hacker news"):
            assert bn.own(i["url"], cat[i["id"]]["domain"]), i
        if i["kind"] == "hacker news":
            sub = bn.host(i["url"])[: -len(cat[i["id"]]["domain"]) - 1] if bn.host(i["url"]).endswith("." + cat[i["id"]]["domain"]) else ""
            assert not sub or sub in bn.COMPANY_SUBDOMAINS, i                # a user's site on the vendor's platform is not the vendor's news
        if i["kind"] == "release":
            assert urllib.parse.urlsplit(i["url"]).hostname == "github.com" and not bn.PRERELEASE.search(i["title"]), i

def test_an_untrusted_feed_cannot_declare_entities_or_a_doctype():
    bomb = '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><rss><channel><item><title>&b;</title><link>https://x.com/a</link><pubDate>Tue, 04 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>'
    assert bn.parse_feed(bomb) == []
    ok = '<rss><channel><item><title>Shipped</title><link>https://x.com/a</link><pubDate>Tue, 04 Nov 2026 10:00:00 GMT</pubDate></item></channel></rss>'
    assert bn.parse_feed(ok) == [("Shipped", "https://x.com/a", "2026-11-04T10:00:00+00:00")]

def test_a_bare_release_version_never_pretends_to_explain_what_changed():
    assert bn.VERSION_ONLY.fullmatch("CrewAI 1.15.36")
    assert bn.release_summary("") is None
    assert bn.release_summary("## What's changed\n- Fix retry handling when a worker reconnects by @author in https://github.com/x/y/pull/1") == "Fix retry handling when a worker reconnects"
    for item in json.loads(paths.NEWS.read_text())["items"]:
        assert item["kind"] != "release" or not bn.VERSION_ONLY.fullmatch(item["title"]), item


# --- oss: Open-source alternatives: rebuilt offline from saved responses, vetted by OpenSSF Scorecard's automated checks, and never accusatory. ---

def test_vetted_projects_come_first_and_every_flag_is_a_finding_not_an_accusation():
    d = json.loads(paths.OSS.read_text())
    for cat, rows in d["categories"].items():
        seen_unvetted = False
        for r in rows:
            if not r["vetted"]: seen_unvetted = True
            assert not (seen_unvetted and r["vetted"]), (cat, r["repo"], "a vetted project ranked below an unvetted one")
            assert r["vetted"] == bool(not r["gate"] and r["scorecard"] and r["scorecard"]["score"] >= 5
                                       and not set(r["flags"]) & {"dangerous CI workflow", "binary files committed", "known vulnerabilities open (OSV)"})
            assert r["gate"] in (None, "no licence stated", "no push in 180 days")
            for f in r["flags"]:
                assert not any(w in f.lower() for w in ("malicious", "honeypot", "scam", "malware", "safe")), f
            if r["scorecard"]:
                assert r["scorecard"]["url"] == "https://scorecard.dev/viewer/?uri=github.com/" + r["repo"] and len(r["scorecard"]["checks"]) == len(d["source"]["checks"]["order"])

def test_social_sources_keep_channel_attention_and_adoption_as_different_claims():
    community, oss = json.loads(paths.COMMUNITY.read_text()), json.loads(paths.OSS.read_text())
    assert community["catalog"] and all("links" in community["entities"][q] or "people" in community["entities"][q]
                                        for qs in community["catalog"].values() for q in qs if q in community["entities"])
    repos = [r for rows in oss["categories"].values() for r in rows]
    assert repos and all(isinstance(r["forks"], int) and isinstance(r["open_issues_and_pull_requests"], int) and isinstance(r["discussions_enabled"], bool) for r in repos)
    for r in repos:
        hn = r["community"]["hacker_news"]
        assert hn["status"] in ("observed", "not_observed", "not_indexed")
        if hn["status"] == "observed":
            assert hn["count"] >= len(hn["items"]) >= 1 and len(hn["window"]) == 2 and hn["fetched_at"]
            assert all(i["url"].startswith("https://github.com/") and i["discussion"].startswith("https://news.ycombinator.com/item?id=") for i in hn["items"])
    html = (paths.ROOT / "web/src/components/cards/catalog.js").read_text()
    assert "repository attention and capability, not use" in html and "Discussion appears only when a dated source record exists" in html and "composite" not in html.lower()


# --- stats: The embeddable stats card says exactly what the deployed site says, and is rebuilt with the data. ---

def test_the_committed_card_is_the_one_the_data_builds_and_its_numbers_are_the_sites():
    before = paths.STATS_SVG.read_text()
    subprocess.run([sys.executable, str(ROOT / "backend/tools/build_stats.py")], check=True, capture_output=True)
    svg = paths.STATS_SVG.read_text()
    assert svg == before, "stats.svg is stale: run backend/tools/build_stats.py"
    t = paths.SITE_DATA.read_text(); site = json.loads(t[t.index("{"):t.rindex("}") + 1])
    assert f'>{len(site["index"]) + site["dir"]["products"]:,}</text><text class="lab" y="30">software products' in svg
    assert f'>{site["dir"]["orgs"]:,}</text><text class="lab" y="30">organizations' in svg
    assert "$" not in svg and "<script" not in svg                     # no spend figure, and an image runs no script
    assert "prefers-reduced-motion:reduce" in svg


# --- events: The factual calendar keeps observed, published and AirStack review dates apart. ---

def test_every_calendar_event_is_factual_dated_and_sourced():
    d = json.loads(paths.EVENTS.read_text()); lo, hi = d["source"]["window"]
    assert d["events"] and all(e["status"] in ("observed", "scheduled", "recheck") and lo <= e["at"] <= hi for e in d["events"])
    for e in d["events"]:
        assert e["precision"] == "day" and e["url"].startswith("https://") and "until" not in e
        if e["status"] == "scheduled":
            assert e["at"] > d["source"]["built_for"] and e["url"].startswith("https://endoflife.date/")
        if e["status"] == "observed":
            assert e["at"] <= d["source"]["built_for"] and e["url"]


# --- pricing: List prices: a price is published only when its quote is on the pricing page and the quote contains the price as written. ---

PAGE = "Plans for every team. Free $0 forever for individuals. Plus $10 per seat/month billed annually. Business $15 per seat/month. Enterprise: contact sales."

def plan(name, price, quote, period="month", unit="user"):
    return {"plan": name, "price": price, "period": period, "unit": unit, "quote": quote}

def test_a_price_is_kept_only_when_its_quote_is_on_the_page_and_contains_it():
    ok, bad = bpricing.verify(PAGE, [plan("Plus", "$10", "Plus $10 per seat/month billed annually"), plan("Business", "$15", "Business $15 per seat/month")])
    assert [p["plan"] for p in ok] == ["Plus", "Business"] and not bad

def test_an_invented_price_a_quote_from_nowhere_or_a_missing_currency_is_refused():
    ok, bad = bpricing.verify(PAGE, [plan("Plus", "$12", "Plus $10 per seat/month billed annually"),          # price not in its quote
                              plan("Team", "$8", "Team $8 per seat/month"),                           # quote not on the page
                              plan("Business", "15", "Business $15 per seat/month")])                 # no currency
    assert not ok and len(bad) == 3

def test_the_plan_must_be_named_in_its_quote_or_right_beside_it():
    ok, _ = bpricing.verify(PAGE, [plan("Free", "$0", "$0 forever for individuals")])                       # the name sits just before the quote
    assert [p["plan"] for p in ok] == ["Free"]
    ok, bad = bpricing.verify(PAGE, [plan("Gold", "$0", "$0 forever for individuals")])
    assert not ok and bad

def test_a_shared_code_hosts_platform_price_is_not_an_unrelated_projects_price():
    from airstack.publication import owned_prices
    prices = {"project": {"url": "https://github.com/pricing", "plans": [plan("Team", "$4", "Team $4")]},
              "github": {"url": "https://github.com/pricing", "plans": [plan("Team", "$4", "Team $4")]},
              "acme": {"url": "https://billing.acme.test/pricing", "plans": [plan("Pro", "$9", "Pro $9")]}}
    homes = {"project": "https://github.com/org/project", "github": "https://github.com/", "acme": "https://www.acme.test/"}
    safe = owned_prices(prices, homes, shared_hosts={"github.com"}, can_publish=lambda url: True)
    assert set(safe) == {"github", "acme"} and "project" not in safe

def test_a_price_is_withheld_when_the_latest_recheck_lost_a_quote():
    from airstack.publication import owned_prices
    q = {"acme": {"url": "https://acme.test/pricing", "plans": [plan("Pro", "$9", "Pro $9")]}}
    assert owned_prices(q, {"acme": "https://acme.test"}, missing={"https://acme.test/pricing"}, can_publish=lambda url: True) == {}

def test_the_published_pricing_snapshot_is_already_the_safe_projection():
    from airstack.publication import public_prices
    prices = json.loads(paths.PRICING.read_text())
    assert public_prices(prices) == prices
    assert [(pid, row["url"]) for pid, row in prices.items() if row["url"].startswith("https://github.com/pricing")] == [
        ("github", "https://github.com/pricing")]


# --- site_assess: Review 5b33e45, C01 and C04: what the static site publishes keeps uncertainty, and is evaluated at an explicit time. ---

def src(f):
    return {"label": f["source"], "date": "", "dated": "checked", "url": f["url"]}

def facts_of(store):
    return {f.id: {"source": f.source, "url": f.url, "source_ts": f.source_ts, "observed_at": f.observed_at} for f in store.facts_for("meet")}

def add(store, metric, value, effective_at=None):
    store.append_fact(entity_id="meet", metric=metric, value=value, source="google.meet.help", url=f"https://support.google.com/meet/{metric}",
                      source_ts=None, observed_at=T0, effective_at=effective_at)

def test_C01_an_unresolved_evaluation_is_never_published_as_keep(store):
    add(store, "supported_languages", LANGS)                              # only one of four requirements has any evidence
    a = bsd.assess(store, facts_of(store), "fireflies", "Business Standard", "Android", "Android", T_EVENT, src)
    assert a["action"] == "unknown" and a["line"] == "Not enough evidence yet."
    assert "aren't included" not in a["reason"] and a["unknown"] >= 2 and a["basis"] is None   # no negative claim from a missing fact

def test_C04_a_future_effective_fact_cannot_justify_a_current_answer(store):
    add(store, "in_person_notes", True, effective_at="2026-09-30T00:00:00Z")
    add(store, "in_person_notes_platforms", ["Android"]); add(store, "supported_languages", LANGS)
    add(store, "listed_editions", ["Business Standard"])
    early = bsd.assess(store, facts_of(store), "fireflies", "Business Standard", "Android", "Android", "2026-08-13T18:00:00Z", src)
    late = bsd.assess(store, facts_of(store), "fireflies", "Business Standard", "Android", "Android", "2026-10-01T00:00:00Z", src)
    assert early["action"] == "unknown" and late["action"] == "retire"
    with pytest.raises(ValueError):
        bsd.assess(store, facts_of(store), "fireflies", "Business Standard", "Android", "Android", None, src)   # no clock, no answer

def test_C02_every_published_answer_carries_its_evaluation_time_and_deadline(store):
    add(store, "supported_languages", LANGS)
    a = bsd.assess(store, facts_of(store), "otter", "Business Starter", "iPhone", "iOS", T_EVENT, src)
    assert a["evaluatedAt"] == T_EVENT and a["freshUntil"] > a["evaluatedAt"]

def test_a_keep_says_it_is_provisional():
    store = Store()
    add(store, "in_person_notes", True); add(store, "in_person_notes_platforms", ["Android"]); add(store, "supported_languages", LANGS)
    add(store, "listed_editions", ["Business Standard"])
    a = bsd.assess(store, facts_of(store), "fireflies", "Business Starter", "Android", "Android", T_EVENT, src)
    assert a["action"] == "keep" and a["basis"].startswith("Provisional")


# --- catalog: The catalog of mainstream paid software: every entry carries what tools/check_catalog.py observed on the live page, and ---

CATALOG = json.loads(paths.CATALOG.read_text())

UNIVERSE = json.loads(paths.UNIVERSE.read_text())

FIELDS = {"id", "name", "category", "homepage", "pricing", "pages", "aliases", "domain", "vendor", "checked"}

MUST_HAVE = ["Gmail", "Slack", "Salesforce", "Notion", "Figma", "Zoom", "ChatGPT", "Cursor", "Linear", "Jira",
             "DocuSign", "Typeform", "Coupa", "Vimeo"]

NEW_CATEGORIES = {"legal-contracts": "Legal and contracts", "forms-surveys": "Forms and surveys", "spend-procurement": "Spend and procurement",
                  "learning": "Learning and training", "video-webinars": "Video and webinars", "it-service": "IT and service desk"}

def host(url):
    return urllib.parse.urlsplit(url).hostname or ""

def test_every_entry_has_the_fields():
    assert len(CATALOG) >= 450
    for e in CATALOG:
        assert FIELDS <= set(e), e.get("id")
        assert all(isinstance(e[k], str) and e[k] for k in ("id", "name", "category", "homepage", "domain", "vendor")), e["id"]
        assert isinstance(e["aliases"], list) and all(isinstance(a, str) and a for a in e["aliases"]), e["id"]
        assert e["homepage"].startswith("https://"), e["id"]
        assert e["domain"] == host(e["homepage"]).removeprefix("www."), e["id"]
        assert set(e["pages"]) == set(KINDS) and all(u is None or u.startswith("https://") for u in e["pages"].values()), e["id"]

def test_ids_are_unique_and_do_not_collide_with_the_universe():
    ids = [e["id"] for e in CATALOG]
    assert len(ids) == len(set(ids))
    assert not set(ids) & {u["id"] for u in UNIVERSE}

def test_no_entry_duplicates_a_universe_name():
    assert not {e["name"].lower() for e in CATALOG} & {u["name"].lower() for u in UNIVERSE}

def test_categories_are_from_the_fixed_list():
    assert {e["category"] for e in CATALOG} == set(CATEGORIES)          # every category, the new ones too, has products

def test_the_new_categories_exist_with_their_names():
    assert {k: CATEGORIES.get(k) for k in NEW_CATEGORIES} == NEW_CATEGORIES

def test_every_kept_entry_records_what_was_observed():
    for e in CATALOG:
        ck = e["checked"]
        assert ck["date"] and isinstance(ck["title_matches"], bool) and isinstance(ck["host_matches"], bool), e["id"]
        assert isinstance(ck["status"], int) and ck["reachable"] in ("yes", BLOCKED), e["id"]
        assert ck["status"] < 400 or (ck["status"] == 403 and ck["reachable"] == BLOCKED), e["id"]
        assert ck["title_matches"] or ck["host_matches"], e["id"]          # the page or its host names the product

def test_pricing_is_a_confirmed_page_or_null_with_a_reason():
    for e in CATALOG:
        ck = e["checked"]
        if e["pricing"] is None:
            assert ck["pricing_null_reason"], e["id"]
        else:
            assert e["pricing"] == ck["pricing_tried"] and 200 <= ck["pricing_status"] < 300, e["id"]

def test_every_page_is_a_confirmed_page_or_null_with_a_reason():
    for e in CATALOG:
        for k in KINDS:
            seen = e["checked"]["pages"][k]
            if e["pages"][k] is None:
                assert seen["null_reason"], (e["id"], k)
            else:
                assert seen["tried"] == e["pages"][k] and isinstance(seen["status"], int) and 200 <= seen["status"] < 300, (e["id"], k)
                assert "null_reason" not in seen and seen["final_url"], (e["id"], k)

def test_no_page_is_on_another_products_domain():
    vendors = {}
    for o in CATALOG:
        vendors.setdefault(reg(o["domain"]), set()).add(o["vendor"])
    for e in CATALOG:
        own = {reg(e["domain"]), reg(host(e["checked"]["final_url"]))}
        for k in KINDS:
            if e["pages"][k] is None:
                continue
            for url in (e["pages"][k], e["checked"]["pages"][k]["final_url"]):     # where it was found and where it landed
                assert owned(url, e, e["checked"]["final_url"]), (e["id"], k, url)
                assert reg(host(url)) in own or not vendors.get(reg(host(url)), set()) - {e["vendor"]}, (e["id"], k, url)

def test_the_products_people_type_first_are_present():
    names = {e["name"].lower() for e in CATALOG}                       # the vendor writes it "Docusign" now
    assert [n for n in MUST_HAVE if n.lower() not in names] == []
