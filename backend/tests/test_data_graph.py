# spec: AS-259 AS-270 AS-286 AS-288 AS-291 AS-292
from conftest import ROOT
import build_feed as bfeed, build_firmographics as bfirmo, build_graph as bg, build_hf as bh, build_marks as bm, build_trust as bt, gzip, json, pytest, re, subprocess, xml.etree.ElementTree as ET
from airstack import fetch, paths
from datetime import datetime


# --- graph: Works with: a link is a vendor's claim on its own page, made by a stated rule, and never drawn without that page; related(tool)'s ---

G = lambda: json.loads(paths.GRAPH.read_text())

def resolve():
    site = bg.paths.read_js(paths.SITE_DATA)
    return bg.resolver(site["index"], site["tools"], json.loads(paths.CATALOG.read_text()),
                       json.loads(paths.UNIVERSE.read_text()), json.loads(paths.DIRECTORY.read_text()))

def test_each_rule_links_the_product_it_should_and_nothing_else():
    r = resolve()
    assert r("Slack") == ("slack", "name") and r("Hubspot") == ("hubspot", "name") and r("Datadog®") == ("datadog", "name")
    assert r("Monday.com") == ("monday-com", "name")
    assert r("MS Teams") == ("microsoft-teams", "alias") and r("Outlook") == ("outlook", "alias") and r("Fireflies.ai") == ("fireflies", "alias")
    assert r("Close.com") == ("close", "domain") and r("Make.com") == ("make", "domain")
    assert r("PostgreSQL") == ("Q192490", "wikidata") and r("Jenkins") == ("Q7491312", "wikidata") and r("Final Cut Pro") == ("Q9587", "wikidata")
    # a maker is not a product: Wikidata's alias for Google is Google Search, and the catalog's alias "meta" is Meta AI
    assert r("Google") == (None, "names a maker") and r("Meta") == (None, "names a maker") and r("Oracle") == (None, "names a maker")
    # names that mean another product on the pages that use them (Apache Spark, Atlassian Bamboo, GNU Make)
    assert r("Spark") == r("Bamboo") == r("Make") == r("Sentry") == (None, "names more than one product")
    # Wikidata labels match exactly, case kept: Eclipse is not ECLIPSE (an oil-field simulator), Edge is not EDGE
    assert r("Eclipse") == (None, "not listed") and r("Edge") == (None, "not listed")
    # Wikidata aliases and websites are not used: CRM is not Cốc Cốc, X is not Vidix, twitter.com is not "Snowflake ID"
    assert r("CRM") == r("X") == r("Twitter.com") == (None, "not listed")
    assert r("Copilot") == (None, "ambiguous") and r("Salesforce.com") == (None, "ambiguous")   # two products answer to it
    assert r(",") == (None, "not a name")

HAND_CHECKED = [   # (product, name as its page writes it, what it links to), each read against the page's quote and the target's record
    ("otter", "Slack", "slack"), ("claude-code", "Jira", "jira"), ("axure-rp", "Jira", "jira"), ("calendly", "Office 365", "microsoft-365"),
    ("hiver", "Monday.com", "monday-com"), ("crewai", "DataDog", "datadog"), ("openlit", "OpenAI Agents SDK", "openai-agents-sdk"),
    ("dashlane", "Datadog®", "datadog"), ("payhawk", "Personio", "personio"), ("agiloft", "DocuSign", "docusign"), ("fathom", "HubSpot", "hubspot"),
    ("Q2720274", "Final Cut Pro", "Q9587"), ("Q869375", "Apple Health", "Q19863865"), ("Q4740694", "Postfix", "Q1121334"),
    ("Q1062467", "Visual Studio", "Q134067"), ("pleo", "Odoo", "Q832300"), ("Q123630818", "Brave Search", "Q107355971"), ("Q1249280", "OpenVPN", "Q509075"),
    # kept as text: the page means another product than the one the name would link to
    ("Q19646047", "Spark", None), ("Q19646047", "Hive", None), ("Q5618801", "Falcon", None), ("Q20739542", "Make", None),
    ("Q116745307", "Sentry", None), ("clerk", "Instant", None), ("Q103793232", "Orca", None), ("melio", "Meta", None), ("avalara", "Sage", None),
    ("readai", "Push to Slack", None)]

def test_a_hand_checked_sample_links_what_each_page_means():
    P = G()["products"]
    for src, name, want in HAND_CHECKED:
        got = [e[1] for e in P[src]["integrates_with"] if e[0] == name]
        assert got == [want], (src, name, got)

def test_no_edge_without_the_page_that_says_it():
    g, chain = G(), json.loads(paths.CHAIN_DATA.read_text())["entities"]
    edges = 0
    for pid, p in g["products"].items():
        said = {}                                                           # (page, quote) -> the names its facts list (one quote can carry several facts)
        for f in chain.get(pid, {}).get("facts", []):
            if f["metric"] == "integrations": said.setdefault((f["url"], f["quote"]), set()).update(str(v).strip().lower() for v in f["value"])
        for name, target, pages, *how in p.get("integrates_with", []):
            assert pages and target != pid, (pid, name)
            for i in pages:
                pg = p["pages"][i]
                assert pg["class"] in ("vendor", "store", "maker") and pg["read"] and pg["verified"] and pg["url"].startswith("http")   # never "other"
                assert name.strip().lower() in said[(pg["url"], pg["quote"])], (pid, name, pg["url"])   # this page's fact names it, with this quote
            if target:
                edges += 1
                assert pid in g["products"][target]["named_by"] and how and how[0] in ("name", "alias", "domain", "wikidata")
    assert edges == g["source"]["counts"]["linked"] > 5000
    for t, p in g["products"].items():                                    # the reverse: every "named by" is an edge on the namer's own page
        assert all(any(e[1] == t for e in g["products"][s]["integrates_with"]) for s in p["named_by"]), t

def test_hubs_are_counted_by_distinct_products_that_name_them():
    g = G()
    hubs = g["hubs"]
    assert hubs[0][:2] == ["slack", "Slack"] and [h[2] for h in hubs] == sorted((h[2] for h in hubs), reverse=True)
    assert all(h[2] == len(g["products"][h[0]]["named_by"]) for h in hubs)

def test_related_names_five_kinds_and_says_seen_together_is_not_available():
    g, oss, site = G(), json.loads(paths.OSS.read_text()), bg.paths.read_js(paths.SITE_DATA)
    k = g["kinds"]
    assert {"covered_by", "integrates_with", "alternative", "open_source", "seen_together"} <= set(k) and all(x["label"] and x["means"] for x in k.values())
    assert k["seen_together"]["available"] is False and "never co-adoption" in k["seen_together"]["means"]
    cats = g["related"]["categories"]
    gated = {r["repo"] for v in oss["categories"].values() for r in v if r["gate"]}
    assert all(r["repo"] not in gated for c in cats.values() for r in c["open_source"])                # below the gate is never an alternative
    assert cats["crm-sales"]["open_source"] and cats["coding-agents"]["open_source"] == []          # only the catalog's categories have candidates
    for pid, p in g["products"].items():
        assert (p["lane"] is None) == (pid not in {m for c in cats.values() for m in c["members"]}), pid
        assert p["lane"] is None or pid in cats[p["lane"]]["members"]
    cov = g["related"]["covered_by"]
    assert set(cov["by_tool"]) == {t["key"] for t in site["tools"]}                                   # meeting notes only, every checked app
    for i in {i for v in cov["by_tool"].values() for i in v}:
        e = cov["edges"][i]
        assert e["by_id"] in ("google-meet", "zoom", "microsoft-teams") and e["fresh_until"] and e["sources"] and all(s["url"] for s in e["sources"])
    starter = [cov["edges"][i] for i in cov["by_tool"]["fireflies"] if cov["edges"][i]["plan"] == "Business Starter"]
    assert starter == []                                                    # Meet's notes are not in Business Starter: not covered


# --- hf: Open models from the Hugging Face Hub: the committed hf.json is exactly what the builder makes offline from the committed raw ---

HF = json.loads(paths.HF.read_text())

def raw_items():
    for f in sorted(bh.RAW.glob("*.json.gz")):
        yield from json.loads(gzip.decompress(f.read_bytes()))["items"]

@pytest.mark.private_data
def test_the_committed_hf_json_is_rebuilt_byte_for_byte_from_the_saved_responses():
    assert bh.render().encode() == paths.HF.read_bytes()

def test_every_task_has_models_and_every_model_links_its_hub_page():
    assert list(HF["tasks"]) == list(bh.TASKS)
    for tag, task in HF["tasks"].items():
        assert task["models"], f"{tag} is empty"
        assert len(task["models"]) <= bh.TOP
        for m in task["models"]:
            assert m["url"] == f"https://huggingface.co/{m['id']}"
            assert isinstance(m["downloads"], int)

@pytest.mark.private_data
def test_a_licence_is_null_or_a_license_tag_the_api_returned():
    tags = {}
    for m in raw_items():
        tags.setdefault(m["id"], set()).update(m.get("tags", []))
    for task in HF["tasks"].values():
        for m in task["models"]:
            assert m["license"] is None or f"license:{m['license']}" in tags[m["id"]], m["id"]
            if m["license"] is None:
                assert not any(t.startswith("license:") for t in tags[m["id"]]), m["id"]


# --- marks: Marks come only from Wikidata's logo on Wikimedia Commons, only under a free licence, with the file's own licence, author and address. ---

def licence(short, link=None, attr_req="false", attr=None):
    """A Commons licence table as the File: page renders it (underscores written as &#95;)."""
    s = lambda k, v: f'<span class="licensetpl&#95;{k}">{v}</span>' if v is not None else ""
    return (f'<table class="licensetpl" style="display:none"> <tbody><tr> <td>{s("short", short)}{s("long", short)}{s("link", link)}'
            f'{s("link&#95;req", "true" if link else "false")}{s("attr&#95;req", attr_req)}{s("attr", attr)} </td></tr></tbody></table>')

def page(*tables, author="Acme Inc.", credit='<a href="https://acme.example">acme.example</a>', restrictions=(), categories=(), status=200, final=None):
    return {"status": status, "read": "2026-11-05T12:00:00+00:00", "final": final, "licences": list(tables), "author": author, "credit": credit,
            "restrictions": sorted(restrictions), "categories": list(categories)}

def test_a_free_licence_or_pd_textlogo_is_kept_and_anything_else_is_left_out_with_its_reason():
    m, why = bm.mark("Acme logo.svg", page(licence("Public domain"), restrictions={"trademarked"}, categories=["PD textlogo", "With trademark"]))
    assert why is None and (m["licence"], m["basis"], m["trademarked"], m["author"], m["credit"]) == ("Public domain", "PD-textlogo", True, "Acme Inc.", "acme.example")
    m, _ = bm.mark("Acme logo.svg", page(licence("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0", "true", "Jane Doe")))
    assert (m["licence"], m["licence_url"], m["attribution_required"], m["attribution"], m["basis"]) == ("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0", True, "Jane Doe", None)
    m, _ = bm.mark("Acme logo.svg", page(licence("GFDL"), licence("CC BY 3.0")))                  # dual-licensed: the free one is the one recorded
    assert m["licence"] == "CC BY 3.0"
    assert bm.mark("x.svg", page(licence("Fair use"))) == (None, "licence not on the free list: Fair use")
    assert bm.mark("x.svg", page(licence("CC BY-NC 4.0")))[0] is None
    flagged = licence("Public domain").replace("</td>", '<span class="licensetpl&#95;nonfree">true</span></td>')
    assert bm.mark("x.svg", page(flagged))[0] is None                       # Commons' non-free flag outranks a free-looking name
    assert bm.mark("x.svg", page()) == (None, "no machine-readable licence on the File: page")
    assert bm.mark("x.svg", page(licence("Public domain"), status=404)) == (None, "File: page not read (status 404)")

def test_the_address_is_commons_own_and_follows_a_renamed_file():
    assert bm.upload_url("Buhl logo.svg") == "https://upload.wikimedia.org/wikipedia/commons/2/21/Buhl_logo.svg"
    m, _ = bm.mark("Old name.svg", page(licence("CC0"), final="https://commons.wikimedia.org/wiki/File:Buhl_logo.svg"))
    assert (m["file"], m["url"], m["page"]) == ("Buhl logo.svg", bm.upload_url("Buhl logo.svg"), "https://commons.wikimedia.org/wiki/File:Buhl_logo.svg")

def test_a_former_or_deprecated_logo_is_never_used():
    st = lambda v, rank="normal", end=False: {"rank": rank, "mainsnak": {"snaktype": "value", "datavalue": {"value": v}},
                                             "qualifiers": {"P582": [{"snaktype": "value", "datavalue": {"value": {"time": "+2026-05-19T00:00:00Z", "precision": 11}}}]} if end else {}}
    assert bm.current_logo({"claims": {"P154": [st("Old.svg", end=True), st("New.svg")]}}) == "New.svg"
    assert bm.current_logo({"claims": {"P154": [st("Bad.svg", "deprecated"), st("Ended.svg", end=True)]}}) is None
    assert bm.current_logo({"claims": {"P154": [st("Normal.svg"), st("Preferred.svg", "preferred")]}}) == "Preferred.svg"

def test_a_file_page_is_read_at_its_own_address_never_through_the_closed_api(monkeypatch):
    seen = []
    html_ = ('<td id="fileinfotpl&#95;aut" class="fileinfo-paramfield">Author</td> <td> <a href="/wiki/User:X">X</a></td>'
             '<td id="fileinfotpl&#95;src">Source</td>\n<td>Own work</td>' + licence("Public domain") +
             '<table class="layouttemplate restrictiontemplate restriction-trademarked"></table><script>"wgCategories":["PD textlogo"],</script>')
    monkeypatch.setattr(bm.fetch, "get", lambda url, **kw: seen.append(url) or (200, html_, {"x-final-url": url}))
    p = bm.page("Acme logo (2020).svg")
    assert seen == ["https://commons.wikimedia.org/wiki/File:Acme_logo_%282020%29.svg"]
    assert (p["author"].strip(), p["credit"], p["restrictions"], p["categories"], len(p["licences"])) == ('<a href="/wiki/User:X">X</a>', "Own work", ["trademarked"], ["PD textlogo"], 1)
    m, _ = bm.mark("Acme logo (2020).svg", p)
    assert (m["author"], m["basis"], m["trademarked"]) == ("X", "PD-textlogo", True)

@pytest.mark.private_data
def test_every_committed_mark_is_free_on_commons_and_no_image_is_in_the_repo():
    d = json.loads(paths.MARKS.read_text())
    assert d["marks"], "no marks built"
    for q, m in d["marks"].items():
        assert re.fullmatch(r"Q\d+", q) and bm.FREE.fullmatch(m["licence"]), (q, m)
        assert m["url"].startswith(bm.UPLOAD) and m["page"].startswith(bm.PAGE) and m["read"], (q, m)
    assert all(re.fullmatch(r"Q\d+", q) and why for q, why in d["dropped"].items())
    tracked = subprocess.run(["git", "ls-files", "data", "*.json"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert not [f for f in tracked if re.search(r"\.(svg|png|jpe?g|gif|webp)$", f, re.I)]   # addresses and licences only, no downloaded marks


# --- trust: Trust for what you would install: OSV records pinned to the version they covered, "reported" only from a MAL- record with its link, ---

FIXTURE = ROOT / "backend" / "tests" / "fixtures" / "trust" / "2026-11-05.json"

BANNED = re.compile(r"\b(malicious|safe|safety|honeypot|scam)\b", re.I)

@pytest.fixture
def built(tmp_path):
    raw = tmp_path / "2026-11-05.json.gz"
    raw.write_bytes(gzip.compress(FIXTURE.read_bytes(), mtime=0))
    out = tmp_path / "trust.json"
    bt.build(raw, out)
    return json.loads(out.read_text()), raw, out

def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values(): yield from strings(v)
    elif isinstance(o, list):
        for v in o: yield from strings(v)

def test_no_verdict_word_is_ever_ours_and_an_empty_answer_is_never_a_clean_bill(built):
    d, _, _ = built
    names = sorted({p["name"] for p in d["packages"].values()}, key=len, reverse=True)
    sources = [n for n, _ in bt.SOURCES.values()]
    for s in strings(d):                                                   # every string AirStack wrote: package and database names masked
        for n in names + sources:
            s = s.replace(n, "")
        assert not BANNED.search(s), s
    assert {p["status"] for p in d["packages"].values()} <= {"reported", "advisories", "none found", "not checked"}
    for p in d["packages"].values():
        if p["status"] == "none found":
            assert p["says"].startswith("No matching advisories found on 2026-11-05 for ") and p["advisories"] == [] and not p["reported"]
        if p["status"] == "not checked":
            assert p["advisories"] is None and p["reported"] is None    # unknown, never an empty list
    assert d["packages"]["npm:safe-env"]["status"] == "none found"          # a package's own name is not our word

def test_only_a_live_mal_record_says_reported_and_it_carries_its_link(built):
    d, _, _ = built
    py = d["packages"]["pypi:alpha-py"]
    assert py["status"] == "reported" and py["reported"] == ["MAL-2026-1"] and "MAL-2026-1" in py["says"]
    mal = next(a for a in py["advisories"] if a["id"] == "MAL-2026-1")
    assert mal["link"] == "https://osv.dev/vulnerability/MAL-2026-1" and mal["source"] == "OpenSSF Malicious Packages" and mal["licence"] == "Apache-2.0"
    assert mal["affected"] == ["versions 2.0.0"]                           # PyPI names compare normalised (Alpha_Py is alpha-py)
    beta = d["packages"]["npm:@beta/cli"]                                  # a withdrawn MAL- record and two advisories: listed, not reported
    assert beta["status"] == "advisories" and beta["reported"] == []
    by = {a["id"]: a for a in beta["advisories"]}
    assert by["MAL-2025-9"]["withdrawn"] == "2026-09-01" and "MAL-2025-9" not in beta["says"]
    assert by["GHSA-bbbb-cccc-dddd"]["severity"] == "HIGH" and by["GHSA-bbbb-cccc-dddd"]["affected"] == ["all versions, < 3.2.0"]
    assert by["CVE-2026-0001"].get("details", "").startswith("not stored") and "severity" not in by["CVE-2026-0001"]   # licence not cleared: id and link only
    assert beta["issues"] == 1 and "1 advisory for @beta/cli@3.1.0 (2 records)" in beta["says"]    # records that alias each other are one issue
    for p in d["packages"].values():
        assert (p["status"] == "reported") == bool(p["reported"])
        for rid in p["reported"] or []:
            assert rid.startswith("MAL-") and rid in {a["id"] for a in p["advisories"] if not a.get("withdrawn")}
        for a in p["advisories"] or []:
            assert a["link"] == f"https://osv.dev/vulnerability/{a['id']}"

def test_every_check_is_pinned_to_the_version_it_covered(built):
    d, _, _ = built
    a = d["packages"]["npm:alpha-js"]                                      # npm moved to 1.2.4; OSV and the attestation were read for 1.2.3
    assert a["version"] == "1.2.4" and a["covers"] is None and a["checked"] is None
    assert a["status"] == "not checked" and a["advisories"] is None and "GHSA-aaaa-bbbb-cccc" not in json.dumps(a)
    assert "alpha-js@1.2.4" in a["says"] and a["provenance"]["state"] == "not checked" and a["provenance"]["version"] == "1.2.4"
    assert d["packages"]["pypi:alpha-py"]["version"] == "2.0.0"            # the highest final release, not the newest upload or the rc
    for p in d["packages"].values():
        if p["status"] != "not checked":
            assert p["covers"] == f"{p['name']}@{p['version']}" and p["provenance"]["version"] == p["version"] and p["checked"] == "2026-11-05"

def test_provenance_is_what_npm_holds_and_pypi_is_not_checked_while_robots_txt_closes_it(built):
    d, _, _ = built
    P = d["packages"]
    assert P["npm:@beta/cli"]["provenance"]["state"] == "attested" and P["npm:@beta/cli"]["provenance"]["types"] == ["SLSA provenance v1", "npm publish attestation"]
    assert "did not re-verify" in P["npm:@beta/cli"]["provenance"]["says"]
    assert P["npm:pubpkg"]["provenance"]["state"] == "absent"
    assert P["pypi:alpha-py"]["provenance"]["state"] == "not checked" and "robots.txt" in P["pypi:alpha-py"]["provenance"]["says"]
    assert not any(p["provenance"] and p["provenance"]["state"] == "verified" for p in P.values())

def test_a_repository_gets_a_package_only_when_npm_points_back(built):
    d, _, _ = built
    R = d["repos"]
    assert R["own/pubpkg"]["packages"] == ["npm:pubpkg"]
    assert R["beta-org/beta"]["packages"] == ["npm:@beta/cli"] and "universe.json" in R["beta-org/beta"]["how"]
    assert R["own/squatted"]["packages"] is None and "someone-else/squat" in R["own/squatted"]["reason"]   # a name alone can belong to someone else
    assert "npm:squat" not in d["packages"]
    assert R["own/app"]["packages"] is None and "private" in R["own/app"]["reason"]
    assert R["own/none"]["packages"] is None and R["own/none"]["reason"] == "no package.json at the repository root"
    assert "saas" not in d["tools"] and d["tools"]["alpha"] == ["npm:alpha-js", "pypi:alpha-py"]
    assert "deps.dev" in d["source"]["closed"]

@pytest.mark.parametrize("repo,want", [({"url": "git+https://github.com/Own/Pkg.git"}, "own/pkg"), ("github:own/pkg", "own/pkg"), ("own/pkg", "own/pkg"),
                                       ("git@github.com:own/pkg.git", "own/pkg"), ("https://github.com/own/pkg/tree/main/x", "own/pkg"),
                                       ("https://gitlab.com/own/pkg", None), ({"url": None}, None), (None, None)])
def test_repository_fields_are_read_as_github_repositories_only(repo, want):
    assert bt.gh_repo(repo) == want

def test_a_saved_run_rebuilds_byte_for_byte(built, tmp_path):
    _, raw, out = built
    again = tmp_path / "again.json"
    bt.build(raw, again)
    assert again.read_bytes() == out.read_bytes()

def test_a_run_keeps_only_the_fields_it_reads(monkeypatch):
    """No maintainer's email and no signature bundle reaches the saved run."""
    pages = {"https://registry.npmjs.org/x/latest": json.dumps({"name": "x", "version": "1.0.0", "repository": "own/x",
                                                                "maintainers": [{"name": "m", "email": "m@example.com"}], "_npmUser": {"email": "m@example.com"}}),
             "https://registry.npmjs.org/-/npm/v1/attestations/x@1.0.0": json.dumps({"attestations": [{"predicateType": "https://slsa.dev/provenance/v1", "bundle": {"sig": "AAAA"}}]})}
    monkeypatch.setattr(bt.fetch, "get", lambda url, headers=None, data=None: (200, pages[url], {}))
    saved = {}; src = bt.live(saved, sleep=0)
    assert bt.version(src, "npm", "x")[0] == "1.0.0"
    assert bt.provenance(src, "npm", "x", "1.0.0", {}, "2026-11-05")["state"] == "attested"
    assert "example.com" not in json.dumps(saved) and "bundle" not in json.dumps(saved)


# --- feed: The changes feed, the badges and the open-data release: well-formed, deterministic, and never carrying a withheld page or page text. ---

A = "{http://www.w3.org/2005/Atom}"

RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

OK, CLOSED, APPLE = "https://vendor.test/changelog/v2", "https://closed.test/blog/post", "https://apps.apple.com/us/app/x/id1"

def news(*items, read="2026-11-05"):
    return {"source": {"read": read}, "items": [{"id": "acme", "name": "Acme", "kind": "changelog", **i} for i in items]}

def events(*evs):
    return {"source": {"built_for": "2026-11-05"}, "events": [{"id": "acme", "name": "Acme", "precision": "day", **e} for e in evs]}

def release():
    return sorted(paths.OPEN_DATA.glob("airstack-*.jsonl.gz"))

def test_the_committed_feed_badges_and_release_are_rebuilt_from_the_published_files():
    out = bfeed.build()
    assert {"changes.atom", "badges.json", "open-data/README.md"} <= set(out) and any(k.endswith(".jsonl.gz") for k in out)
    stale = [k for k, v in out.items() if not (paths.SITE / k).exists() or not bfeed.same(k, v, (paths.SITE / k).read_bytes())]   # built by another process: same inputs, same output
    assert not stale, f"stale: {stale}; run backend/tools/build_feed.py"

def test_the_feed_is_well_formed_atom_and_every_entry_has_an_id_a_title_a_link_and_a_date():
    feed = ET.parse(paths.FEED).getroot()                      # a parse error fails here
    assert feed.tag == A + "feed"
    for t in ("id", "title", "updated", "author/" + A + "name"):
        assert (feed.findtext(A + t) or "").strip(), t
    assert any(l.get("rel") == "self" and l.get("href") == "https://airstack.bot/changes.atom" for l in feed.findall(A + "link"))
    es = feed.findall(A + "entry")
    assert 0 < len(es) <= 200
    import build_pages
    slugs = {p["slug"] for p in (lambda a: build_pages.built(a, build_pages.own_prices(a, json.loads(paths.PRICING.read_text()))))(build_pages.products()).values()}
    ids, dates = [], []
    for e in es:
        ids.append(e.findtext(A + "id")); dates.append(e.findtext(A + "updated"))
        assert ids[-1].startswith("tag:airstack.bot,2026:") and (e.findtext(A + "title") or "").strip()
        assert RFC3339.match(dates[-1]) and datetime.fromisoformat(dates[-1])
        links = {l.get("rel"): l.get("href") for l in e.findall(A + "link")}
        assert links["alternate"].startswith(("https://", "http://")) and fetch.published(links["alternate"])
        if "related" in links:                                             # the product's page, and only a page that is built
            m = re.fullmatch(r"https://airstack\.bot/p/([a-z0-9-]+)/", links["related"])
            assert m and m.group(1) in slugs, links["related"]
    assert len(set(ids)) == len(ids) and dates == sorted(dates, reverse=True)
    assert feed.findtext(A + "updated") == dates[0]                        # dated by its newest entry, never by the clock

def test_a_withheld_page_never_becomes_an_entry(monkeypatch):
    monkeypatch.setattr(fetch, "_closed", {CLOSED})                       # what the robots.txt sweep withholds
    n = news({"title": "Shown", "url": OK, "date": "2026-11-04T10:00:00+00:00"}, {"title": "Robots closed", "url": CLOSED, "date": "2026-11-04T11:00:00+00:00"},
             {"title": "Terms bar reading", "url": APPLE, "date": "2026-11-04T12:00:00+00:00"})
    ev = events({"at": "2026-11-03", "status": "observed", "kind": "end of life", "title": "Acme 1: end of life", "url": CLOSED})
    got = bfeed.changes(n, ev, {})
    assert [x["title"] for x in got] == ["Shown"]
    assert CLOSED.encode() not in bfeed.atom(got, "2026-11-05") and b"apps.apple.com" not in bfeed.atom(got, "2026-11-05")

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
    feed = ET.fromstring(bfeed.atom(got, "2026-11-05"))                      # escaped, and the control character is gone
    assert feed.findtext(f"{A}entry/{A}title") == "Release <2> & notes" and feed.findtext(A + "updated") == "2026-11-04T10:00:00Z"
    assert feed.find(f"{A}entry/{A}link[@rel='related']").get("href") == "https://airstack.bot/p/acme/"
    assert bfeed.changes(n, ev, {})[0]["page"] is None                       # no page, no related link: never a link to a 404
    assert bfeed.atom(got, "2026-11-05") == bfeed.atom(bfeed.changes(n, ev, {"acme": "acme"}), "2026-11-05")
    many = news(*({"title": f"r{i}", "url": f"https://vendor.test/r{i}", "date": f"2026-11-0{1 + i % 4}T{i % 24:02d}:00:00Z"} for i in range(250)))
    capped = bfeed.changes(many, events(), {})
    assert len(capped) == 200 and [x["updated"] for x in capped] == sorted((x["updated"] for x in capped), reverse=True)

def test_the_release_holds_only_published_facts_and_no_stored_page_text():
    chain = json.loads(paths.CHAIN_DATA.read_text())
    shown = {(pid, f["metric"], f["url"], f["quote"], json.dumps(f["value"], sort_keys=True)) for pid, e in chain["entities"].items() for f in e["facts"]}
    files = release()
    assert files
    newest = gzip.decompress(files[-1].read_bytes()).decode().splitlines()
    assert len(newest) > 1000
    for f in files:
        for line in gzip.decompress(f.read_bytes()).decode().splitlines():
            r = json.loads(line)
            assert tuple(sorted(r)) == tuple(sorted(bfeed.OPEN_FIELDS)) and fetch.published(r["url"])
            assert len(r["quote"].split()) <= 25 and r["licence"] in {bfeed.LICENCE, bfeed.LICENCE_WIKIMEDIA}
            if f == files[-1]:
                assert (r["id"], r["metric"], r["url"], r["quote"], json.dumps(r["value"], sort_keys=True)) in shown, line[:200]
    src = (ROOT / "backend" / "tools" / "build_feed.py").read_text()
    assert not re.search(r"sqlite3|airstack-market\.db|raw_items|airstack\.corpus", src)   # it cannot read stored pages: it never opens the database

def test_a_withheld_page_leaves_the_release_too(monkeypatch):
    chain = {"entities": {"acme": {"name": "Acme", "facts": [{"metric": "platforms", "value": ["macOS"], "quote": "Download for macOS", "url": u, "host": "vendor.test",
                                                           "retrieved": "2026-11-04"} for u in (OK, CLOSED)]}}}
    monkeypatch.setattr(fetch, "_closed", {CLOSED})
    assert [json.loads(l)["url"] for l in bfeed.open_lines(chain)] == [OK]

def test_badges_are_deterministic_self_contained_and_say_what_the_profile_says():
    profiles = json.loads(paths.PROFILES.read_text())
    data = json.loads((paths.BADGES).read_text())
    import build_pages
    slugs = {k: p["slug"] for k, p in build_pages.products().items()}
    assert bfeed.badges(profiles, slugs) == bfeed.badges(profiles, slugs) == data and len(data["badges"]) == len(profiles)
    for pid in sorted(profiles)[::173] + ["claude-code"]:
        s = slugs[pid]; svg = bfeed.badge_svg(data, s)
        assert svg == bfeed.badge_svg(data, s) and ET.fromstring(svg).tag == "{http://www.w3.org/2000/svg}svg"
        assert "prefers-color-scheme:dark" in svg and not re.search(r"<script|<a\b|href|@import|url\(|<image|<foreignObject|\{\{", svg)
        assert set(re.findall(r"https?://[^\"' )]+", svg)) == {"http://www.w3.org/2000/svg"}   # no font, script or image from anywhere
        p = profiles[pid]; n = p["facts"]
        read = max(c["checked"] for c in p.values() if isinstance(c, dict))
        assert f"AirStack &#183; {n} fact{'' if n == 1 else 's'} from its own pages &#183; read {read}" in svg


# --- firmographics: Firmographics are records: each value names its source, link and day; sources that disagree are all shown; what is unknown stays out. ---

T = lambda d, p=11: {"time": f"+{d}T00:00:00Z", "precision": p}

Q = lambda q: {"id": q}

def st(v, rank="normal", **quals):
    return {"rank": rank, "mainsnak": {"snaktype": "value", "datavalue": {"value": v}},
            "qualifiers": {p: [{"snaktype": "value", "datavalue": {"value": x}}] for p, x in quals.items()}}

def wd(claims, refs=None, read="2026-11-05T10:00:00+00:00", **items):
    return {"items": {"Q1": {"status": 200, "read": read, "label": "Acme", "claims": claims}, **items}, "refs": refs or {}}

COUNTRIES = {"Q30": {"label": "United States", "P297": ["US"], "P17": ["Q30"]}, "Q183": {"label": "Germany", "P297": ["DE"], "P17": ["Q183"]},
             "Q10": {"label": "Berlin", "P17": ["Q183"], "P297": []}}

def gleif(country="US", parent=None):
    rec = {"id": "LEI0000000000000000A", "attributes": {"entity": {"legalName": {"name": "ACME GMBH"}, "status": "ACTIVE", "jurisdiction": "DE",
                                                                   "headquartersAddress": {"country": country, "city": "Somewhere"}},
                                                        "registration": {"status": "ISSUED"}}}
    out = {"records": {"LEI0000000000000000A": {"status": 200, "read": "2026-11-05T11:00:00+00:00", "record": rec}}, "parents": {}}
    if parent:
        out["parents"]["LEI0000000000000000A"] = {"status": 200, "read": "2026-11-05T11:00:00+00:00",
                                                 "record": {"id": parent, "attributes": {"entity": {"legalName": {"name": "PARENT AG"}}}}}
    return out

def test_a_date_keeps_its_own_precision_and_a_year_never_gains_a_day():
    assert bfirmo.date_of(T("1986-01-01", 9)) == "1986"
    assert bfirmo.date_of(T("1986-03-00", 10)) == "1986-03"
    assert bfirmo.date_of(T("1986-03-15", 11)) == "1986-03-15"
    assert bfirmo.date_of(T("1980-01-01", 8)) is None                          # a decade is not a founding year
    assert bfirmo.date_of({"time": "-0400-01-01T00:00:00Z", "precision": 9}) is None and bfirmo.date_of(None) is None

def test_an_ended_parent_or_listing_is_former_and_a_deprecated_statement_never_counts():
    r = bfirmo.org_record("Q1", None, wd({
        "P571": [st(T("1900-01-01", 9), "deprecated"), st(T("1986-01-01", 9))],
        "P749": [st(Q("Q2"), P580=T("2010-00-00", 9), P582=T("2016-00-00", 9))],
        "P414": [st(Q("Q3"), P249="ACME", P582=T("2020-05-01")), st(Q("Q4"), "deprecated", P249="OLD")]},
        {"Q2": {"label": "Old Parent", "P1278": []}, "Q3": {"label": "Nasdaq"}, "Q4": {"label": "Gone"}}), {}, {})
    assert [x["value"] for x in r["founded"]] == ["1986"]
    assert r["parent"] == [{"value": "Old Parent", "id": "Q2", "since": "2010", "former": True, "until": "2016", "source": "Wikidata",
                            "url": "https://www.wikidata.org/wiki/Q1#P749", "read": "2026-11-05"}]
    assert [(x["exchange"], x["ticker"], x.get("former")) for x in r["listed"]] == [("Nasdaq", "ACME", True)]
    preferred = bfirmo.org_record("Q1", None, wd({"P571": [st(T("1990-01-01", 9)), st(T("1991-01-01", 9), "preferred")]}), {}, {})
    assert [x["value"] for x in preferred["founded"]] == ["1991"] and "disagree" not in preferred

def test_sources_that_disagree_are_all_shown_and_named():
    claims = {"P159": [st(Q("Q10"))], "P1278": [st("LEI0000000000000000A")], "P749": [st(Q("Q20"))]}
    refs = {**COUNTRIES, "Q20": {"label": "Mother Corp", "P1278": ["LEIMOTHER00000000000"]}}
    r = bfirmo.org_record("Q1", None, wd(claims, refs), gleif("US", parent="LEIPARENT00000000000"), {})
    assert [(x["source"], x["code"], x["value"]) for x in r["hq_country"]] == [("Wikidata", "DE", "Germany"), ("GLEIF", "US", "United States")]
    assert {x["source"] for x in r["parent"]} == {"Wikidata", "GLEIF"} and r["disagree"] == ["hq_country", "parent"]
    assert r["legal_entity"][0]["url"] == "https://search.gleif.org/#/record/LEI0000000000000000A"
    same = bfirmo.org_record("Q1", None, wd(claims, {**refs, "Q20": {"label": "Mother Corp", "P1278": ["LEIPARENT00000000000"]}}), gleif("DE", parent="LEIPARENT00000000000"), {})
    assert "disagree" not in same and len(same["hq_country"]) == 2           # agreeing sources are both still shown
    two = bfirmo.org_record("Q1", None, wd({"P571": [st(T("1986-01-01", 9)), st(T("1988-06-01", 10))]}), {}, {})
    assert [x["value"] for x in two["founded"]] == ["1986", "1988-06"] and two["disagree"] == ["founded"]

def test_unknown_stays_out_with_its_reason():
    r = bfirmo.org_record("Q1", "https://www.acme.de/", wd({}), {}, {})
    assert set(r) == {"gaps"} and r["gaps"]["legal_entity"] == "no LEI on Wikidata"
    assert "terms have not been reviewed" in r["gaps"]["domain_registered"]
    assert bfirmo.org_record("Q9", None, wd({}), {}, {})["gaps"]["wikidata"].startswith("the Wikidata item was not read")
    for v in json.loads(paths.FIRMOGRAPHICS.read_text())["orgs"].values():
        for k, rows in v.items():
            if k not in ("gaps", "disagree"):
                assert rows and all(x.get("value") or x.get("exchange") for x in rows), (k, rows)   # never an empty or zero value

def _web(monkeypatch, tmp_path, routes):
    seen = []
    def get(url, headers=None, **kw):
        seen.append(url)
        for prefix, body in routes.items():
            if url.startswith(prefix):
                return (200, body, {}) if body is not None else (404, "", {})
        return 404, "", {}
    monkeypatch.setattr(bfirmo.fetch, "get", get); monkeypatch.setattr(bfirmo.time, "sleep", lambda s: None)
    for k in ("WD", "GL", "RD"):
        monkeypatch.setattr(bfirmo, k, tmp_path / k)
    return seen

def test_every_request_is_on_a_path_robots_txt_opens_and_gleif_is_asked_only_for_recorded_leis(monkeypatch, tmp_path):
    ent = {"entities": {"Q1": {"id": "Q1", "labels": {"en": {"value": "Acme"}}, "claims": {
        "P159": [st(Q("Q10"))], "P1278": [st("LEI0000000000000000A"), st("not an lei")], "P856": [st("https://acme.example")]}}}}
    ttl = {"Q10": 'wd:Q10 wdt:P17 wd:Q183 ;\n\trdfs:label "Berlin"@en ;\n\trdfs:label "Berlin"@de .',
           "Q183": 'wd:Q183 wdt:P17 wd:Q183 ;\n\twdt:P297 "DE" ;\n\trdfs:label "Deutschland (en-gb)"@en-gb ;\n\trdfs:label "Germany"@en .'}
    seen = _web(monkeypatch, tmp_path, {bfirmo.ENTITY.format("Q1"): json.dumps(ent), **{bfirmo.SIMPLE.format(q): t for q, t in ttl.items()},
                                        bfirmo.GLEIF: json.dumps({"data": [gleif()["records"]["LEI0000000000000000A"]["record"] | {"relationships": {}}]})})
    raw = bfirmo.fetch_wikidata(["Q1"])
    assert raw["refs"]["Q10"]["P17"] == ["Q183"] and raw["refs"]["Q183"] | {"read": 0} == {"status": 200, "read": 0, "label": "Germany", "P17": ["Q183"], "P297": ["DE"], "P1278": []}
    assert set(raw["items"]["Q1"]["claims"]) == {"P159", "P1278"}             # only the statements used are kept
    leis = [bfirmo.value(s) for s in bfirmo.statements(raw["items"]["Q1"], "P1278")]
    bfirmo.fetch_gleif(leis)
    bfirmo.fetch_rdap([bfirmo.domain(u)[0] for u in ("https://acme.com/", "https://www.acme.org") if bfirmo.domain(u)[0]])
    assert [u for u in seen if u.startswith(bfirmo.GLEIF)] == [f"{bfirmo.GLEIF}?filter[lei]=LEI0000000000000000A&page[size]=100"]
    assert [u for u in seen if "rdap" in u] == ["https://rdap.verisign.com/com/v1/domain/acme.com", "https://rdap.publicinterestregistry.org/rdap/domain/acme.org"]
    assert all(u.startswith(("https://www.wikidata.org/wiki/Special:EntityData/", bfirmo.GLEIF, *bfirmo.RDAP.values())) for u in seen)
    assert not [u for u in seen if re.search(r"/w/api\.php|/sparql|query\.wikidata|Special:FilePath", u)]
    assert sorted(p.name for p in tmp_path.rglob("*.json.gz")) == [f"{bfirmo.now()[:10]}.json.gz"] * 3   # one file per source per run

def test_rdap_asks_only_reviewed_registries_and_only_for_a_domain_of_its_own():
    assert bfirmo.domain("https://www.acme.com/") == ("acme.com", None)
    assert bfirmo.domain("https://github.com/acme")[0] is None                   # a page on another site says nothing about the company
    assert bfirmo.domain("https://acme.herokuapp.com/")[0] is None
    assert bfirmo.domain("https://acme.de/") == (None, "not read: the .de registry's terms have not been reviewed")
    assert bfirmo.domain(None) == (None, "no website on record")

@pytest.mark.private_data
def test_every_committed_record_names_its_source_link_and_day():
    d = json.loads(paths.FIRMOGRAPHICS.read_text())
    assert d["source"]["wikidata"]["license"] == d["source"]["gleif"]["license"] == "CC0 1.0" and d["source"]["sec_edgar"].startswith("not read")
    hosts = {"Wikidata": "https://www.wikidata.org/wiki/Q", "GLEIF": "https://search.gleif.org/#/record/", "RDAP": tuple(bfirmo.RDAP.values())}
    assert d["orgs"]
    for o, v in d["orgs"].items():
        assert set(v) <= {"founded", "hq_country", "parent", "listed", "legal_entity", "domain_registered", "disagree", "gaps"}
        for k in set(v) - {"disagree", "gaps"}:
            for x in v[k]:
                assert x["url"].startswith(hosts[x["source"]]) and re.fullmatch(r"\d{4}-\d\d-\d\d", x["read"]), (o, k, x)
        for k in v.get("disagree", []):
            assert len(v[k]) > 1, (o, k)
