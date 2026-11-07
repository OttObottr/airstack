# spec: AS-140 AS-236 AS-238 AS-274 AS-289 AS-326 AS-334
from conftest import ROOT
import build_chain_data as bcd, build_movers as bm, corroborate as co, gzip, json, pathlib, pytest, re, sqlite3, urllib.error
import xml.etree.ElementTree as ET
from airstack import fetch, paths
from airstack.connectors import registries as reg
from build_movers import Raw
from datetime import date


# --- chain_data: The chain of custody: every link is derived from stored records, unknown never counts as independent, agreement is counted honestly. ---

def make_db(path):
    c = sqlite3.connect(path)
    c.executescript("""
      CREATE TABLE raw_items(url TEXT, status INT, fetched_at TEXT, body_hash TEXT);
      CREATE TABLE rechecks(id INTEGER PRIMARY KEY, url TEXT, checked_at TEXT, outcome TEXT, note TEXT, quotes_ok INT, quotes_total INT);
      CREATE TABLE calls(call_ref TEXT, model TEXT, ts TEXT, kind TEXT);
      CREATE TABLE entities(id TEXT, name TEXT);
      CREATE TABLE facts(id INTEGER PRIMARY KEY, entity_id TEXT, metric TEXT, value TEXT, url TEXT, source TEXT);
      CREATE TABLE fact_provenance(fact_id INT, call_ref TEXT, quote TEXT);
      CREATE TABLE verifications(url TEXT, metric TEXT, quote TEXT, call_ref TEXT, ok INT, checked_at TEXT);""")
    c.execute("INSERT INTO entities VALUES('acme','Acme')")
    for i, (url, val, q, call) in enumerate([("https://acme.test/", ["Slack", "Notion"], "Works with Slack and Notion", "r1"),
                                             ("https://chromewebstore.google.com/x", ["Slack"], "Integrates with Slack", "r2"),
                                             ("https://blog.other.test/review", ["Slack"], "It syncs to Slack", "r3"),
                                             ("https://acme.test/pricing", "Plans from free", "Plans from free", "r4")], 1):
        m = "x.integrations" if isinstance(val, list) else "x.pricing_basis"
        c.execute("INSERT INTO facts VALUES(?,?,?,?,?,?)", (i, "acme", m, json.dumps(val), url, "muse.catalog"))
        c.execute("INSERT INTO fact_provenance VALUES(?,?,?)", (i, call, q))
        c.execute("INSERT INTO verifications VALUES(?,?,?,?,1,'2026-11-04T01:00:00Z')", (url, m, q, call))
        c.execute("INSERT INTO raw_items VALUES(?,200,'2026-11-04T00:00:00Z',?)", (url, "a" * 64))
        c.execute("INSERT INTO calls VALUES(?, 'muse-spark-1.3', '2026-11-04T00:30:00Z', 'call')", (call,))
    c.execute("INSERT INTO rechecks(url, checked_at, outcome, note, quotes_ok, quotes_total) VALUES('https://acme.test/','2026-11-04T02:00:00Z','unchanged','the server reports the page unchanged',1,1)")
    c.commit(); c.close()

def test_every_link_of_the_chain_comes_from_stored_records_and_unknown_is_never_independent(tmp_path):
    make_db(tmp_path / "m.db")
    d = bcd.build(tmp_path / "m.db", universe=[{"id": "acme", "homepage": "https://acme.test/"}])
    facts = {(f["metric"], f["host"]): f for f in d["entities"]["acme"]["facts"]}
    home = facts[("integrations", "acme.test")]
    assert home["class"] == "vendor" and facts[("integrations", "chromewebstore.google.com")]["class"] == "store"
    assert facts[("integrations", "blog.other.test")]["class"] == "other"                  # not tied to the vendor: NOT independent
    assert home["extracted"] == "2026-11-04T00:30:00Z" and home["verified"] == "2026-11-04" and home["hash"] == "a" * 12
    assert not ({"call", "model"} & home.keys())
    assert home["recheck"] == {"at": "2026-11-04", "outcome": "unchanged", "note": "the server reports the page unchanged"}
    assert facts[("integrations", "chromewebstore.google.com")]["recheck"] is None         # never re-checked: says so, not "ok"
    assert home["agree"] == ["blog.other.test", "chromewebstore.google.com"] and home["agree_independent"] == []
    assert facts[("pricing_basis", "acme.test")]["agree"] == []                              # a page's own words have no agreement to count

def test_only_a_listed_third_party_counts_as_independent(tmp_path):
    make_db(tmp_path / "m.db"); c = sqlite3.connect(tmp_path / "m.db")
    c.execute("UPDATE facts SET url='https://9to5google.com/story' WHERE id=3"); c.commit(); c.close()
    d = bcd.build(tmp_path / "m.db", universe=[{"id": "acme", "homepage": "https://acme.test/"}])
    home = next(f for f in d["entities"]["acme"]["facts"] if f["host"] == "acme.test" and f["metric"] == "integrations")
    assert home["agree_independent"] == ["9to5google.com"]

def test_a_price_never_reaches_the_chain(tmp_path):
    make_db(tmp_path / "m.db"); c = sqlite3.connect(tmp_path / "m.db")
    c.execute("UPDATE fact_provenance SET quote='Plans from $29 a month' WHERE fact_id=4"); c.commit(); c.close()
    d = bcd.build(tmp_path / "m.db", universe=[{"id": "acme", "homepage": "https://acme.test/"}])
    assert not any(f["metric"] == "pricing_basis" for f in d["entities"]["acme"]["facts"])

def test_a_page_that_lost_a_quote_is_withheld_until_it_is_re_extracted(tmp_path):
    db = tmp_path / "m.db"; make_db(db); c = sqlite3.connect(db)
    c.execute("INSERT INTO rechecks(url, checked_at, outcome, note, quotes_ok, quotes_total) VALUES(?,?,?,?,?,?)",
              ("https://acme.test/", "2026-11-05T02:00:00Z", "changed_quotes_missing", "one quote is no longer on the page", 0, 1))
    c.commit(); c.close()
    d = bcd.build(db, universe=[{"id": "acme", "homepage": "https://acme.test/"}])
    assert all(f["url"] != "https://acme.test/" for f in d["entities"]["acme"]["facts"])


# --- corroboration: Registry corroboration: the vendor's own package registry entries and GitHub repo are a SECOND RECORD from the same origin, compared value ---

REGISTRY_FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "registry"

PYPI, NPM, GH = co.PYPI.format("acme"), co.NPM.format("@acme/sdk"), "repos/acme/acme"

TOOL = {"id": "acme", "homepage": "https://acme.test/", "pypi": ["acme"], "npm": ["@acme/sdk"], "github": "acme/acme"}

SAAS = {"id": "notes-app", "homepage": "https://notes.test/", "pypi": [], "npm": [], "github": None}

def envelope(url, fixture):
    if fixture is None:
        return {"url": url, "fetched_at": "2026-11-04T12:00:00Z", "status": 404, "body": None, "error": "HTTP 404"}
    return {"url": url, "fetched_at": "2026-11-04T12:00:00Z", "status": 200, "body": json.loads((REGISTRY_FIX / fixture).read_text()), "error": None}

def fetchers(pypi="pypi_acme.json", npm="npm_acme_busl.json", github="github_acme_apache.json"):
    files = {PYPI: pypi, NPM: npm, co.reg.GITHUB_API + GH: github}
    return (lambda url: co.project(envelope(url, files[url]))), (lambda path, jq: envelope(co.reg.GITHUB_API + path, files[co.reg.GITHUB_API + path]))

def run(facts, **fixtures):
    out = co.build([TOOL, SAAS], {"acme": {"facts": facts}}, *fetchers(**fixtures))
    return out, {(c["metric"], json.dumps(c["value"])): {r["source"]: r for r in c["registry"]} for c in out["claims"]}

@pytest.mark.parametrize("text, ids", [
    ("Every piece is MIT-licensed, built by hundreds of contributors in the open.", {"MIT"}),
    ("This project is licensed under the Apache License, Version 2.0.", {"Apache-2.0"}),
    ("Apache 2.0 licensed.", {"Apache-2.0"}), ("Apache-2.0", {"Apache-2.0"}),
    ("The framework is free to use under the BSD-2 license", {"BSD-2-Clause"}), ("BSD-3-Clause", {"BSD-3-Clause"}),
    ("AGPL-3.0-only", {"AGPL-3.0"}), ("GNU Lesser General Public License v3 (LGPLv3)", {"LGPL-3.0"}), ("GPL-3.0-or-later", {"GPL-3.0"}),
    ("Apache Software License", {"Apache"}),                       # a classifier names the family, not the version
    ("MIT OR Apache-2.0", {"MIT", "Apache-2.0"}), ("UNLICENSED", {"Proprietary"}), ("BUSL-1.1", {"BUSL-1.1"}),
    ("Apache-2.0-derivative license", set()), ("Complies with Dify Open Source License", set()),
    ("SEE LICENSE IN LICENSE.md", set()), ("NOASSERTION", set()), ("", set()), (None, set())])
def test_license_text_and_registry_fields_normalise_to_spdx_and_an_unknown_name_is_not_observed(text, ids):
    assert co.spdx(text) == ids

def test_a_family_matches_its_versions_and_nothing_else():
    assert co.same_license("Apache-2.0", "Apache") and co.same_license("BSD", "BSD-3-Clause") and co.same_license("MIT", "MIT")
    assert not co.same_license("Apache-2.0", "MIT") and not co.same_license("BSD-2-Clause", "BSD-3-Clause") and not co.same_license("GPL-3.0", "LGPL-3.0")

def test_an_agreeing_and_a_disagreeing_license_are_both_recorded_with_both_values():
    out, by = run([{"metric": "license", "value": "MIT licensed"}])
    rec = by[("license", '"MIT licensed"')]
    assert rec["pypi"]["agrees"] is True and rec["pypi"]["registry_value"] == "MIT" and rec["pypi"]["raw"] == "license_expression: MIT"
    assert rec["github"]["agrees"] is False and rec["github"]["registry_value"] == "Apache-2.0" and rec["github"]["claim"] == "MIT"
    assert rec["npm"]["agrees"] is False and rec["npm"]["registry_value"] == "BUSL-1.1"
    assert rec["pypi"]["url"] == "https://pypi.org/project/acme/" and rec["npm"]["url"] == "https://www.npmjs.com/package/@acme/sdk"
    assert rec["github"]["url"] == "https://github.com/acme/acme" and rec["pypi"]["checked"] == "2026-11-04"
    assert out["summary"]["by_metric"]["license"] == {"claims": 1, "with_twin": 1, "agreeing": 0, "disagreeing": 1, "no_twin": 0, "not_comparable": 0}

def test_a_claim_naming_no_single_license_is_not_comparable_and_a_classifier_beats_a_pasted_license_text():
    out, by = run([{"metric": "license", "value": "Apache-2.0-derivative license"}, {"metric": "license", "value": "Apache 2.0"}], pypi="pypi_classifier_only.json")
    assert ("license", '"Apache-2.0-derivative license"') not in by and out["summary"]["by_metric"]["license"]["not_comparable"] == 1
    p = by[("license", '"Apache 2.0"')]["pypi"]
    assert p["agrees"] is True and p["registry_value"] == "Apache" and p["raw"] == "License :: OSI Approved :: Apache Software License"

def test_open_source_agrees_only_with_an_osi_license_and_no_license_on_file_is_not_observed():
    _, by = run([{"metric": "open_source", "value": True}])
    rec = by[("open_source", "true")]
    assert rec["pypi"]["agrees"] is True and rec["github"]["agrees"] is True and rec["pypi"]["registry_value"] == "MIT (OSI-approved)"
    assert rec["npm"]["agrees"] is False and rec["npm"]["registry_value"] == "BUSL-1.1 (not OSI-approved)"
    _, by = run([{"metric": "open_source", "value": True}], github="github_noassertion.json")
    assert "github" not in by[("open_source", "true")]                    # GitHub could not name the license: no record, not "closed source"

def test_languages_and_platforms_can_match_but_never_dispute():
    out, by = run([{"metric": "sdk_languages", "value": ["Python", "Go", "Rust", "TypeScript"]}, {"metric": "platforms", "value": ["Linux", "Windows", "AWS"]}])
    assert by[("sdk_languages", '"Python"')]["pypi"]["raw"] == "Programming Language :: Python :: 3"
    assert by[("sdk_languages", '"Go"')]["github"]["raw"] == "language: Go"
    assert by[("sdk_languages", '"TypeScript"')]["npm"]["raw"] == "types: dist/index.d.ts"
    assert ("sdk_languages", '"Rust"') not in by                            # not shown is not observed: no package lists every SDK
    assert set(by[("platforms", '"Linux"')]) == {"pypi", "npm"}            # an explicit classifier and npm's os field
    assert ("platforms", '"Windows"') not in by                             # "OS Independent" and "!win32" name no system it runs on
    assert all(r["agrees"] for c in out["claims"] if c["metric"] in ("sdk_languages", "platforms") for r in c["registry"])
    m = out["summary"]["by_metric"]
    assert m["platforms"]["not_comparable"] == 1 and m["sdk_languages"]["disagreeing"] == m["platforms"]["disagreeing"] == 0

def test_a_failed_read_is_a_failure_not_a_disagreement_and_a_tool_without_registries_says_so():
    out, by = run([{"metric": "license", "value": "MIT"}], npm=None)
    assert "npm" not in by[("license", '"MIT"')] and out["failures"] == [{"tool": "acme", "source": "npm", "url": "https://www.npmjs.com/package/@acme/sdk", "error": "HTTP 404"}]
    assert out["no_registry"] == {"notes-app": "no PyPI or npm package and no GitHub repository listed in data/universe.json"}

def test_saved_envelopes_drop_what_is_not_read_and_offline_replay_reproduces_the_build(tmp_path, monkeypatch):
    monkeypatch.setattr(co.reg, "http_fetch", lambda url, sleep=None: envelope(url, {PYPI: "pypi_acme.json", NPM: "npm_acme_busl.json"}[url]))
    monkeypatch.setattr(co.reg, "gh_run", lambda path, jq, sleep=None: envelope(co.reg.GITHUB_API + path, "github_acme_apache.json"))
    facts = {"acme": {"facts": [{"metric": "license", "value": "MIT"}, {"metric": "sdk_languages", "value": ["Python"]}]}}
    online = co.build([TOOL], facts, *co.recording(tmp_path, sleep=lambda s: None))
    raw = Raw(tmp_path)
    assert co.build([TOOL], facts, raw.fetch, raw.run) == online and len(raw.used) == 3
    saved = json.loads(co.raw_path(PYPI, tmp_path).read_text())
    assert set(saved["body"]) == {"info"} and "description" not in saved["body"]["info"] and saved["projection"].startswith("info.{")

def chain_db(tmp_path):
    make_db(tmp_path / "m.db"); c = sqlite3.connect(tmp_path / "m.db")
    for i, m, v, q in [(5, "x.license", "MIT licensed", "MIT licensed"), (6, "x.open_source", True, "Open source"), (7, "x.sdk_languages", ["Python", "Rust"], "SDKs for Python and Rust")]:
        c.execute("INSERT INTO facts VALUES(?,?,?,?,?,?)", (i, "acme", m, json.dumps(v), "https://acme.test/", "muse.catalog"))
        c.execute("INSERT INTO fact_provenance VALUES(?,?,?)", (i, "r1", q))
    c.commit(); c.close()
    return tmp_path / "m.db"

def test_registry_records_merge_into_the_chain_never_into_agree_independent_and_are_counted_apart(tmp_path):
    db = chain_db(tmp_path)
    before = bcd.build(db, universe=[TOOL], corroboration={})
    corr = co.build([TOOL], before["entities"], *fetchers())
    after = bcd.build(db, universe=[TOOL], corroboration=corr)
    facts = {f["metric"]: f for f in after["entities"]["acme"]["facts"] if f["host"] == "acme.test"}
    assert [(r["source"], r["agrees"]) for r in facts["license"]["registry"]] == [("pypi", True), ("npm", False), ("github", False)]
    assert [(r["claim"], r["source"]) for r in facts["sdk_languages"]["registry"]] == [("python", "pypi")]     # Rust: not observed
    strip = lambda d: [{k: v for k, v in f.items() if k != "registry"} for e in d["entities"].values() for f in e["facts"]]
    assert strip(after) == strip(before)                                   # agree and agree_independent are untouched by registry records
    assert all(f["agree_independent"] == [] for e in after["entities"].values() for f in e["facts"])
    s = after["summary"]
    assert s["registry_second_record"] == 1 and s["registry_disputed"] == 2      # sdk_languages matches; license and open_source are disputed
    assert s["labels"] == {"registry_second_record": "matches a second record (vendor-published registry)", "registry_disputed": "disputed by a registry record"}
    assert "same vendor" in s["registry_note"] and "not independent" in s["registry_note"]

def test_the_chain_builds_unchanged_when_corroboration_json_is_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(bcd, "CORROBORATION", tmp_path / "absent.json")
    d = bcd.build(chain_db(tmp_path), universe=[TOOL])
    assert all(f["registry"] == [] for e in d["entities"].values() for f in e["facts"])
    assert d["summary"]["registry_second_record"] == 0 and d["summary"]["registry_disputed"] == 0 and d["summary"]["facts"] == 7


# --- independent_records: Independent records: what a platform measures itself (a registry's registration date, Wikimedia pageviews, GDELT article counts), read ---

DAY = date(2026, 11, 5)

UNIVERSE = [{"id": "acme", "name": "Acme", "homepage": "https://www.acme.com/", "hn_query": '"Acme Cloud"'},
            {"id": "devtool", "name": "Devtool", "homepage": "https://devtool.dev/", "hn_query": None},
            {"id": "ghtool", "name": "Ghtool", "homepage": "https://github.com/org/ghtool", "hn_query": "Ghtool"},
            {"id": "brit", "name": "Brit", "homepage": "https://brit.co.uk/", "hn_query": None}]

CATALOG = [{"id": "quiet", "name": "Quiet", "domain": "quiet.io", "homepage": "https://quiet.io/"},
           {"id": "acme", "name": "Acme Again", "domain": "elsewhere.com", "homepage": "https://elsewhere.com/"}]   # the universe entry wins

WIKIDATA = {("acme.com", "acme"): {"Q1"}, ("devtool.dev", "devtool"): {"Q2", "Q3"}, ("quiet.io", "quiet"): {"Q4"}, ("brit.co.uk", "brit"): {"Q5"}}

BOOT = {"publication": "2026-10-28T22:00:04Z", "services": [[["com", "net"], ["https://rdap.verisign.com/com/v1/"]],
                                                            [["dev"], ["https://pubapi.registry.google/rdap/"]], [["uk"], ["https://rdap.nominet.uk/uk/"]]]}

RDAP_ACME = {"ldhName": "ACME.COM", "events": [{"eventAction": "registration", "eventDate": "1995-06-28T04:00:00Z"},
                                               {"eventAction": "expiration", "eventDate": "2027-06-27T04:00:00Z"}],
             "notices": [{"title": "Terms of Service", "links": [{"rel": "terms-of-service", "href": "https://www.verisign.com/legal-center/rdap-terms/"}]}],
             "entities": [{"roles": ["registrant"], "vcardArray": ["vcard", [["fn", {}, "text", "Jane Doe"]]]}], "nameservers": [{"ldhName": "NS1.ACME.COM"}]}

PV = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Acme_%28software%29/monthly/20251101/20261031"

WEB = {co.IANA_RDAP: BOOT, "https://rdap.verisign.com/com/v1/domain/acme.com": RDAP_ACME,
       co.ENTITY.format("Q1"): {"entities": {"Q1": {"id": "Q1", "sitelinks": {"enwiki": {"title": "Acme (software)"}}, "claims": {"P571": ["1995"]}}}},
       co.ENTITY.format("Q4"): {"entities": {"Q4": {"id": "Q4", "sitelinks": {"frwiki": {"title": "Quiet"}}}}},
       co.ENTITY.format("Q5"): {"entities": {"Q5": {"id": "Q5", "sitelinks": {"enwiki": {"title": "Brit (app)", "badges": ["Q70893996"]}}}}},
       PV: {"items": [{"timestamp": "2025110100", "views": 1995, "agent": "user"}, {"timestamp": "2025120100", "views": 0, "agent": "user"}]},
       co.gdelt_url('"Acme Cloud"'): {"timeline": [{"series": "Article Count", "data": [{"date": "20260801T000000Z", "value": 1990, "norm": 9},
                                                                                         {"date": "20260802T000000Z", "value": 5, "norm": 9}]}]},
       co.gdelt_url("Ghtool"): 429}

def web(routes=WEB):
    asked = []
    def get(url, headers=None, timeout=25):
        asked.append(url)
        v = routes.get(url, 404)
        return (v, "", {}) if isinstance(v, int) else (200, json.dumps(v), {})
    return get, asked

def second(routes=WEB):
    get, asked = web(routes)
    return {s: co.read_second(s, UNIVERSE, CATALOG, DAY, get, sleep=lambda s: None, wikidata=WIKIDATA) for s in co.SECOND}, asked

def no_registry(*a):
    raise AssertionError("no registry is read for these tools")

def test_a_registration_date_pageviews_and_news_volume_corroborate_and_dispute_nothing():
    batches, _ = second()
    facts = {"acme": {"facts": [{"metric": "founded_year", "value": 1995, "agree": [], "agree_independent": []},       # = the registration year
                                {"metric": "customers_claimed", "value": "1995", "agree": [], "agree_independent": []},  # = the pageviews
                                {"metric": "integrations_count", "value": 1995, "agree": [], "agree_independent": []}]}}  # = the news volume
    out = co.build(UNIVERSE, facts, no_registry, no_registry, batches)
    t = out["independent"]["tools"]["acme"]
    assert (t["domain_registered"]["value"], t["wikipedia_views"]["value"], t["news_articles"]["value"]) == ("1995-06-28", 1995, 1995)
    assert out["rates"]["corroborated"] == 0 and out["rates"]["corroborated_facts"] == [] and out["rates"]["single_record"] == 3
    assert out["rates"]["disputed"] == 0 and out["claims"] == []
    src = out["independent"]["sources"]
    assert src["wikipedia"]["kind"] == src["gdelt"]["kind"] == "attention" and all("not adoption" in src[s]["note"] for s in ("wikipedia", "gdelt"))
    assert "neither confirms nor disputes a founding year" in src["rdap"]["note"]
    gdelt_terms_url = re.search(r"https://\S+", src["gdelt"]["license"]).group(0)
    assert src["wikipedia"]["license"] == "CC0-1.0" and fetch.host(gdelt_terms_url) == "gdeltproject.org" and src["rdap"]["read"] == "2026-11-05"

def test_unknown_is_null_with_its_reason_never_zero():
    batches, _ = second()
    t = co.build(UNIVERSE, {}, no_registry, no_registry, batches)["independent"]["tools"]
    nulls = {(tid, f): r["reason"] for tid, rs in t.items() for f, r in rs.items() if r["value"] is None}
    assert nulls[("ghtool", "news_articles")].startswith("GDELT returned no timeline (HTTP 429)")             # rate-limited: not observed
    assert "shared host" in nulls[("ghtool", "domain_registered")] and "no RDAP service for .io" in nulls[("quiet", "domain_registered")]
    assert nulls[("devtool", "news_articles")] == "no curated news query (hn_query in data/universe.json)"
    assert nulls[("devtool", "wikipedia_views")] == "2 Wikidata items share this product's homepage host and English name"
    assert nulls[("quiet", "wikipedia_views")] == "Wikidata lists no English Wikipedia article"
    assert nulls[("brit", "wikipedia_views")] == "the English Wikipedia sitelink is a redirect, so its views are not the article's"
    assert all(r["value"] != 0 for rs in t.values() for r in rs.values())
    assert t["acme"]["wikipedia_views"]["monthly"] == [1995, 0]                                           # a measured zero month is kept
    empty = dict(WEB) | {co.gdelt_url('"Acme Cloud"'): {}, PV: 404}                                         # GDELT's bare {} and no pageview data
    t = co.build(UNIVERSE, {}, no_registry, no_registry, second(empty)[0])["independent"]["tools"]["acme"]
    assert t["news_articles"]["value"] is None and "not zero" in t["news_articles"]["reason"] and t["wikipedia_views"]["value"] is None

def test_a_registry_whose_terms_bar_republishing_or_were_not_reviewed_is_never_asked():
    batches, asked = second()
    rdap = [u for u in asked if "rdap" in u]
    assert rdap == [co.IANA_RDAP, "https://rdap.verisign.com/com/v1/domain/acme.com"]
    assert not any("Brit_%28app%29" in u for u in asked)                                                    # a redirect's views are never asked for
    t = batches["rdap"]["targets"]
    assert t["devtool"] == {"domain": "devtool.dev", "reason": "pubapi.registry.google: its terms bar republishing (see excluded)"}
    assert t["brit"] == {"domain": "brit.co.uk", "reason": "rdap.nominet.uk: terms not reviewed, so not read"}
    assert "pubapi.registry.google" in co.EXCLUDED and {"Visual Studio Marketplace", "Docker Hub", "App Store and iTunes Search"} <= set(co.EXCLUDED)
    assert not any(h in u for u in asked for h in ("marketplace.visualstudio.com", "hub.docker.com", "apple.com"))

def test_each_source_is_one_gzipped_file_per_run_holding_only_what_is_read_and_the_build_replays_it_byte_for_byte(tmp_path):
    batches, _ = second()
    paths = [co.save_second(b, tmp_path) for b in batches.values()]
    assert [p.relative_to(tmp_path).as_posix() for p in paths] == ["rdap-records-raw/2026-11-05.json.gz", "wikipedia-records-raw/2026-11-05.json.gz", "gdelt-records-raw/2026-11-05.json.gz"]
    first = [p.read_bytes() for p in paths]
    assert [co.save_second(b, tmp_path).read_bytes() for b in batches.values()] == first                    # deterministic bytes (gzip mtime 0)
    saved = json.loads(gzip.decompress(first[0]))["responses"]["https://rdap.verisign.com/com/v1/domain/acme.com"]["body"]
    assert set(saved) == {"ldhName", "events", "terms"} and "Jane Doe" not in json.dumps(saved)              # no contact data kept
    assert json.loads(gzip.decompress(first[1]))["responses"][co.ENTITY.format("Q1")]["body"] == {"id": "Q1", "enwiki": "Acme (software)", "redirect": False}
    live = co.dumps(co.build(UNIVERSE, {}, no_registry, no_registry, batches))
    assert co.dumps(co.build(UNIVERSE, {}, no_registry, no_registry, co.load_second(tmp_path))) == live
    assert co.load_second(tmp_path / "nothing") == {s: None for s in co.SECOND}

def test_only_an_independent_page_corroborates_and_a_registry_dispute_is_counted_as_disputed():
    claims = [{"tool": "acme", "metric": "license", "value": "MIT", "registry": [{"source": "github", "agrees": False}]},
              {"tool": "acme", "metric": "sdk_languages", "value": "Go", "registry": [{"source": "github", "agrees": True}]}]
    facts = {"acme": {"facts": [{"metric": "license", "value": "MIT", "agree": ["acme.com"], "agree_independent": []},
                                {"metric": "sdk_languages", "value": ["Go", "Rust"], "agree": [], "agree_independent": []},
                                {"metric": "integrations", "value": ["Slack"], "agree": ["acme.com"], "agree_independent": []},
                                {"metric": "platforms", "value": ["Android"], "url": "https://acme.com/a", "agree": ["9to5google.com"], "agree_independent": ["9to5google.com"]},
                                {"metric": "free_plan", "value": True, "agree": [], "agree_independent": []}]}}
    r = co.rates(facts, claims)
    assert {k: r[k] for k in ("facts", "corroborated", "disputed", "second_record", "single_record")} == \
           {"facts": 5, "corroborated": 1, "disputed": 1, "second_record": 2, "single_record": 1}
    assert r["corroborated_rate"] == 0.2 and r["corroborated_facts"] == [{"tool": "acme", "metric": "platforms", "value": ["Android"],
                                                                         "url": "https://acme.com/a", "independent_hosts": ["9to5google.com"]}]

def test_the_chain_builds_unchanged_with_independent_records_and_rates_present(tmp_path):
    db = chain_db(tmp_path)
    plain = bcd.build(db, universe=[TOOL], corroboration={"claims": []})
    full = co.build([], bcd.build(db, universe=[TOOL], corroboration={})["entities"], no_registry, no_registry, second()[0])
    assert full["independent"]["tools"] and full["rates"]["facts"] == 7
    assert bcd.build(db, universe=[TOOL], corroboration=full) == plain

def test_a_slow_robots_txt_is_still_an_answer(monkeypatch):
    waits = []
    def open_(req, timeout=0):
        waits.append((req.full_url, timeout))
        raise urllib.error.HTTPError(req.full_url, 404, "missing", {}, None)
    fetch._robots.clear()
    monkeypatch.setattr(fetch, "_resolve", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    monkeypatch.setattr(fetch, "_open", open_)
    assert fetch.allowed("https://slow.test/api") is True
    assert waits == [("https://slow.test/robots.txt", fetch.ROBOTS_TIMEOUT)] and fetch.ROBOTS_TIMEOUT >= 20    # GDELT answers 404 after ~14 s


# --- movers: Movers dataset: delta math, weekly series, the primary package rule, registry parsing, null-with-reason (never 0 for missing), ---

MOVERS_FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "movers"

END = "2026-11-02"

WINDOW = reg.make_window(END)

def env(name):
    return json.loads((MOVERS_FIX / name).read_text())

def fetcher(*names):
    """A fake fetcher that serves recorded envelopes by URL and fails loudly on anything else."""
    by_url = {e["url"]: e for e in map(env, names)}
    def fetch(url, *_):
        assert url in by_url, f"unexpected fetch {url}"
        return by_url[url]
    return fetch

def runner(*names):
    f = fetcher(*names)
    return lambda path, jq: f(reg.GITHUB_API + path)

def rows(values, end=END):
    from datetime import date, timedelta
    e = date.fromisoformat(end)
    return [{"day": (e - timedelta(days=len(values) - 1 - i)).isoformat(), "downloads": v} for i, v in enumerate(values)]

# ---------------------------------------------------------------- delta math

def test_week_delta_sums_the_two_weeks_and_rounds_to_one_decimal():
    d = reg.week_delta(rows([10] * 7 + [13] * 7), END)
    assert d == {"value": 91, "prior": 70, "delta_pct": 30.0}
    assert reg.week_delta(rows([3] * 7 + [1, 1, 1, 1, 1, 1, 2]), END)["delta_pct"] == round((8 - 21) / 21 * 100, 1) == -61.9

def test_week_delta_prior_zero_gives_null_delta_not_infinity():
    d = reg.week_delta(rows([0] * 7 + [5] * 7), END)
    assert d["value"] == 35 and d["prior"] == 0 and d["delta_pct"] is None and "prior 7 days were 0" in d["delta_reason"]

def test_week_delta_only_uses_the_14_days_ending_on_end_date():
    d = reg.week_delta(rows([999] * 5 + [1] * 14 + [999] * 3, end="2026-11-05"), END)
    assert d == {"value": 7, "prior": 7, "delta_pct": 0.0}

def test_missing_days_are_null_with_reason_never_zero_filled():
    r = rows([5] * 14); del r[10]                                            # a hole in the last week
    d = reg.week_delta(r, END)
    assert d["value"] is None and "no row for 2026-10-30" in d["reason"]
    r = rows([5] * 14); del r[2]                                             # a hole in the prior week: real total, no comparison
    d = reg.week_delta(r, END)
    assert d["value"] == 35 and d["prior"] is None and d["delta_pct"] is None and "no row for 2026-10-22" in d["delta_reason"]

def test_zero_days_count_as_a_reporting_gap_when_the_source_writes_0_for_missing():
    r = rows([5, 0] + [5] * 12)
    assert reg.week_delta(r, END)["delta_pct"] is not None                  # taken at face value by default
    d = reg.week_delta(r, END, zero_is_gap=True)
    assert d["value"] == 35 and d["prior"] is None and "0 downloads on 2026-10-21" in d["delta_reason"]
    assert reg.week_delta(rows([5] * 13 + [0]), END, zero_is_gap=True)["value"] is None

# ---------------------------------------------------------------- parsing recorded responses

def test_npm_range_parsing():
    r = reg.fetch_npm_range("cline", fetcher("npm_range_cline.json"))
    assert r["package"] == "cline" and r["end"] == END and len(r["rows"]) == 30
    assert r["url"] == "https://api.npmjs.org/downloads/range/last-month/cline" and r["fetched_at"].endswith("Z")
    d = reg.week_delta(r["rows"], END, zero_is_gap=True)
    assert d["value"] == 98595 and d["delta_pct"] is None and "2026-10-20, 2026-10-21" in d["delta_reason"]   # npm wrote 0s for those days

def test_npm_unknown_package_is_null_with_reason_and_still_cites_the_url():
    r = reg.fetch_npm_range("airstack-movers-no-such-package-0", fetcher("npm_range_missing_package.json"))
    assert r["value"] is None and "HTTP 404" in r["reason"] and r["url"].startswith("https://api.npmjs.org/") and r["fetched_at"]

def test_pypi_overall_parsing():
    r = reg.fetch_pypi_overall("aider-chat", fetcher("pypi_overall_aider-chat.json"))
    assert r["url"] == "https://pypistats.org/api/packages/aider-chat/overall?mirrors=false"
    assert [x["day"] for x in r["rows"]] == sorted(x["day"] for x in r["rows"]) and r["end"] == "2026-11-03"
    assert reg.week_delta(r["rows"], END) == {"value": 69192, "prior": 65827, "delta_pct": 5.1}

def test_hn_counts_parsing_and_exact_query_and_window_in_the_url():
    h = reg.hn_counts('"Claude Code"', WINDOW, fetcher("hn_claude_code_last7.json", "hn_claude_code_prior7.json"))
    assert (h["value"], h["prior"], h["delta"], h["query"]) == (89, 103, -14, '"Claude Code"')
    assert "query=%22Claude+Code%22" in h["url"] and "typoTolerance=false" in h["url"] and "hitsPerPage=0" in h["url"]
    assert "created_at_i%3E1793059199%2Ccreated_at_i%3C1793664000" in h["url"]     # [2026-10-27 00:00, 2026-11-03 00:00) UTC
    assert h["prior_url"] != h["url"] and h["fetched_at"] and h["prior_fetched_at"]

def test_rate_limited_fetch_retries_once_then_records_null_reason(monkeypatch):
    calls, slept = [], []
    def urlopen(req, timeout):
        calls.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {"Retry-After": "2"}, None)
    monkeypatch.setattr(reg.urllib.request, "urlopen", urlopen)
    e = reg.http_fetch("https://pypistats.org/api/packages/x/overall?mirrors=false", sleep=slept.append, now=lambda: "2026-11-04T00:00:00Z")
    assert len(calls) == 2 and slept == [2] and e["body"] is None and "429" in e["error"]
    r = reg.fetch_pypi_overall("x", lambda url: e)
    assert r["value"] is None and "rate-limited" in r["reason"]

def test_github_repo_parsing():
    g = reg.github_repo("openai/codex", runner("gh_repo_codex.json", "gh_releases_codex.json"))
    assert g["stars"] == 133060 and g["pushed_at"] == "2026-11-04T04:02:18Z" and g["url"] == "https://api.github.com/repos/openai/codex"
    assert g["last_release"] == "rust-v0.166.0" and g["last_release_at"] == "2026-10-29T19:47:53Z"   # newest NON-prerelease
    assert g["releases_30d"] == 20 and g["releases_30d_capped"] is True and "delta" not in json.dumps(g)
    p = reg.github_repo("pgvector/pgvector", runner("gh_repo_pgvector.json", "gh_releases_pgvector.json"))
    assert p["last_release"] is None and p["last_release_reason"] == "no GitHub releases published" and p["releases_30d"] == 0

def test_monorepo_last_release_is_the_tools_own_package_tag():
    rel = lambda tag, at: {"tag_name": tag, "name": tag, "draft": False, "prerelease": False, "published_at": at, "created_at": at, "html_url": "https://github.com/x/y"}
    body = [rel("@scope/other@3.0.1", "2026-11-02T10:00:00Z"), rel("ai@7.0.1", "2026-11-02T09:00:00Z"), rel("langchain-core==1.7.4", "2026-11-02T08:00:00Z")]
    def run(path, jq):
        b = {"full_name": "x/y", "stargazers_count": 5, "pushed_at": "2026-11-02T00:00:00Z", "archived": False} if path == "repos/x/y" else body
        return {"url": reg.GITHUB_API + path, "fetched_at": "2026-11-03T00:00:00Z", "status": 200, "body": b, "error": None}
    assert reg.github_repo("x/y", run, ["ai"])["last_release"] == "ai@7.0.1"
    assert reg.github_repo("x/y", run, ["langchain"])["last_release"] == "@scope/other@3.0.1"     # "langchain-core" is not "langchain"
    assert reg.github_repo("x/y", run, ["langchain-core"])["last_release"] == "langchain-core==1.7.4"
    assert reg.github_repo("x/y", run)["releases_30d"] == 3

# ---------------------------------------------------------------- the built dataset

TINY = [{"id": "cline", "name": "Cline", "lane": "coding-agents", "npm": ["cline"], "pypi": [], "github": "openai/codex", "hn_query": '"Claude Code"', "homepage": "https://cline.bot"},
        {"id": "aider", "name": "Aider", "lane": "coding-agents", "npm": [], "pypi": ["aider-chat"], "github": None, "hn_query": None, "homepage": "https://aider.chat/"},
        {"id": "otter", "name": "Otter", "lane": "meeting-notes", "npm": [], "pypi": [], "github": None, "hn_query": '"Claude Code"', "homepage": "https://otter.ai"}]

def _tiny():
    f = fetcher("npm_range_cline.json", "npm_range_26w_cline.json", "pypi_overall_aider-chat.json", "hn_claude_code_last7.json", "hn_claude_code_prior7.json")
    return bm.build(TINY, f, runner("gh_repo_codex.json", "gh_releases_codex.json"))

def test_a_tool_without_a_registry_gets_null_and_a_reason_never_zero():
    m = _tiny(); t = {x["id"]: x["signals"] for x in m["tools"]}
    assert t["aider"]["npm_7d"] == {"value": None, "reason": "no npm package"}
    assert t["aider"]["github"] == {"value": None, "reason": "no public GitHub repository"}
    assert t["aider"]["hn_7d"] == {"value": None, "reason": "name too generic to count reliably"}
    for k in ("npm_7d", "pypi_7d", "github"):
        assert t["otter"][k] == {"value": None, "reason": "SaaS app: no public package registry"}
    assert t["otter"]["hn_7d"]["value"] == 89                                  # a SaaS app still gets its (real) HN count
    used = ("npm_range_cline.json", "npm_range_26w_cline.json", "pypi_overall_aider-chat.json", "hn_claude_code_last7.json", "hn_claude_code_prior7.json",
            "gh_repo_codex.json", "gh_releases_codex.json")
    assert m["window"] == WINDOW and m["generated_at"] == max(env(n)["fetched_at"] for n in used)   # from the data, not the clock
    assert m["lanes"] == [{"lane": "coding-agents", "tools": 2, "with_downloads_delta": 1, "with_hn_counts": 1},
                          {"lane": "meeting-notes", "tools": 1, "with_downloads_delta": 0, "with_hn_counts": 1}]

def _numbers_without_provenance(node, path="signals", cited=False):
    """Every dict holding a non-null number must name the url it came from and when it was fetched. The items of a list (a weekly
    series) are cited by the dict that holds the list; nothing else inherits."""
    bad = []
    if isinstance(node, dict):
        own = str(node.get("url", "")).startswith("https://") and bool(node.get("fetched_at"))
        nums = [k for k, v in node.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if nums and not (own or cited):
            bad.append(f"{path}: {nums}")
        if "query" in node and node.get("prior") is not None and not (node.get("prior_url") and node.get("prior_fetched_at")):
            bad.append(f"{path}: HN prior count without its own url")       # HN's two weeks are two requests
        for k in ("value", "series", "primary", "last7"):
            if k in node and node[k] is None and not node.get("reason"):
                bad.append(f"{path}: null {k} without a reason")
        for k, v in node.items():
            bad += _numbers_without_provenance(v, f"{path}.{k}", own and isinstance(v, list))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            bad += _numbers_without_provenance(v, f"{path}[{i}]", cited)
    return bad

@pytest.mark.private_data
def test_every_number_in_a_built_movers_json_has_a_url_and_fetched_at():
    committed = json.loads(bm.OUT.read_text())
    for m in (_tiny(), committed):
        assert m["generated_at"] and m["window"]["last7"] and m["window"]["prior7"]
        assert not [b for t in m["tools"] for k in ("signals", "weeks", "packages") for b in _numbers_without_provenance(t[k], f"{t['id']}.{k}")]
    ids = [t["id"] for t in json.loads(bm.UNIVERSE.read_text())]
    assert [t["id"] for t in committed["tools"]] == ids and len(set(ids)) == len(ids)
    assert _numbers_without_provenance({"series": [{"week": "2026-11-02", "downloads": 5}]})          # the checker itself can fail
    assert not _numbers_without_provenance({"url": "https://x", "fetched_at": "t", "series": [{"week": "2026-11-02", "downloads": 5}]})

@pytest.mark.private_data
def test_offline_rebuild_from_committed_raw_reproduces_movers_json_exactly():
    run = bm.latest_run(bm.RAW)
    movers, used = bm.build_from_raw(run, bm.UNIVERSE)
    assert bm.dumps(movers) == bm.OUT.read_text()
    saved = json.loads(gzip.decompress(run.read_bytes()))
    assert [p.name for p in bm.RAW.iterdir()] == [run.name]                    # ONE run file is the record (git keeps the older ones)
    assert used == set(saved)                                                  # every saved response is used, none missing
    for url, e in saved.items():
        assert e["url"] == url and e["fetched_at"].endswith("Z")

def test_every_universe_entry_has_a_declared_lane_and_https_pages():
    universe = json.loads(bm.UNIVERSE.read_text())
    for t in universe:
        assert t["lane"] in bm.LANES, (t["id"], t["lane"])
        assert t["homepage"].startswith("https://"), t["id"]
        assert set(t["pages"]) == {"pricing", "docs", "integrations", "security"}, t["id"]
        for kind, url in t["pages"].items():
            assert url is None or url.startswith("https://"), (t["id"], kind, url)
            assert url is not None or t["pages_null_reasons"].get(kind), (t["id"], kind, "null page without a reason")
    with pytest.raises(ValueError, match="not declared"):
        bm.build([{**TINY[0], "lane": "no-such-lane"}], None, None)

def test_a_rebound_from_a_trough_week_is_flagged_by_the_tools_own_recent_level():
    """Week-over-week growth must be evaluated against the four-week baseline."""
    from datetime import date, timedelta
    end = date.fromisoformat(END)
    per_week = [120_000, 125_000, 118_000, 130_000, 123_000, 38_000, 80_000]      # oldest first: four normal weeks, a normal one, a trough, a rebound
    daily = [{"day": (end - timedelta(days=7 * (len(per_week) - 1 - i) + (6 - k))).isoformat(), "downloads": total // 7}
             for i, total in enumerate(per_week) for k in range(7)]
    d = reg.week_delta(daily, END)
    assert d["delta_pct"] > 100 and d["vs_base_pct"] < -30 and d["base_weeks"] == 4, d

def test_the_baseline_needs_two_full_earlier_weeks_and_never_invents_one():
    short = reg.week_delta(rows([10] * 7 + [12] * 7), END)
    assert "vs_base_pct" not in short and "base" not in short                  # only two weeks of data: no baseline, no claim

# ---------------------------------------------------------------- AS-289: 26 weeks of history

def test_weeks_are_26_iso_weeks_ending_with_the_week_that_holds_the_last_day():
    s = reg.week_series(rows([7] * 200), END)                                  # END, 2026-11-02, is a Monday
    assert len(s) == 26 and s[0]["week"] == "2026-05-11" and all(date.fromisoformat(w["week"]).weekday() == 0 for w in s)
    assert s[-2] == {"week": "2026-10-26", "downloads": 49, "days": 7, "partial": False}
    assert s[-1] == {"week": "2026-11-02", "downloads": 7, "days": 1, "partial": True}          # the week in progress: one day observed
    assert reg.weeks_span(END) == "2026-05-11:2026-11-02"
    later = reg.week_series(rows([7] * 200 + [1000] * 3, end="2026-11-05"), END)               # days after the window's end are not counted
    assert later == s

def test_a_week_with_no_observation_is_null_never_zero_and_a_short_one_is_partial():
    s = reg.week_series(rows([5] * 21), END, 5)                                # data from Tuesday 13 Oct
    assert [(w["week"], w["downloads"], w["days"], w["partial"]) for w in s] == [
        ("2026-10-05", None, 0, True), ("2026-10-12", 30, 6, True), ("2026-10-19", 35, 7, False), ("2026-10-26", 35, 7, False), ("2026-11-02", 5, 1, True)]
    gap = rows([5] * 7 + [0] * 7 + [5] * 2 + [0] + [5] * 4 + [5], end=END)  # npm writes 0 for days it has no data for
    s = reg.week_series(gap, END, 4, zero_is_gap=True)
    assert [(w["downloads"], w["days"]) for w in s] == [(35, 7), (None, 0), (30, 6), (5, 1)]
    assert reg.week_series(gap, END, 4)[1] == {"week": "2026-10-19", "downloads": 0, "days": 7, "partial": False}   # PyPI: a 0 is a real 0

def test_the_built_dataset_carries_each_tracked_packages_weeks_from_its_own_response():
    m = _tiny(); t = {x["id"]: x for x in m["tools"]}
    npm = t["cline"]["weeks"]["npm"]
    assert npm["package"] == "cline" and npm["url"] == "https://api.npmjs.org/downloads/range/2026-05-11:2026-11-02/cline" and len(npm["series"]) == 26
    assert t["aider"]["weeks"]["pypi"]["url"] == t["aider"]["signals"]["pypi_7d"]["url"] and t["aider"]["weeks"].keys() == {"pypi"}
    assert t["otter"]["weeks"] == {} and t["otter"]["packages"] == {}
    oct19 = next(w for w in npm["series"] if w["week"] == "2026-10-19")
    assert oct19["partial"] and oct19["days"] == 4                            # npm's 19-21 Oct reporting gap is not observed, not 0
    assert t["cline"]["packages"]["npm"] == {"tracked": "cline", "primary": "cline", "rule": "only-package", "candidates": []}

# ---------------------------------------------------------------- AS-236: the package that is the product

ACME = {"id": "acme", "name": "Acme", "lane": "agent-frameworks", "npm": ["acme"], "pypi": ["acme-ai"], "github": "acme/acme", "hn_query": None,
        "homepage": "https://acme.dev", "siblings": {"npm": ["@acme/sdk"], "pypi": ["acme_sdk"]}}

SPAN = reg.weeks_span(END)

def _served(readme_lines, per_day, failed=()):
    """Fake responses for ACME: npm and pypistats days at `per_day[package]` downloads a day, a README with `readme_lines`."""
    npm = lambda p: {"start": "x", "end": END, "package": p, "downloads": rows([per_day[p]] * 200)}
    pypi = lambda p: {"data": [{"date": r["day"], "downloads": r["downloads"], "category": "without_mirrors"} for r in rows([per_day[p]] * 200)]}
    bodies = {reg.NPM_RANGE.format(span="last-month", pkg="acme"): npm("acme"), reg.PYPI_OVERALL.format(pkg="acme-ai"): pypi("acme-ai"),
              reg.NPM_RANGE.format(span=SPAN, pkg="acme"): npm("acme"), reg.NPM_RANGE.format(span=SPAN, pkg="@acme/sdk"): npm("@acme/sdk"),
              reg.PYPI_OVERALL.format(pkg="acme_sdk"): pypi("acme_sdk"), bm.README.format(repo="acme/acme"): {"install_lines": readme_lines},
              reg.GITHUB_API + "repos/acme/acme": {"full_name": "acme/acme", "stargazers_count": 1, "pushed_at": None, "archived": False},
              reg.GITHUB_API + f"repos/acme/acme/releases?per_page={reg.RELEASES_PER_PAGE}": []}
    def fetch(url):
        assert url in bodies, f"unexpected fetch {url}"
        bad = url in failed
        return {"url": url, "fetched_at": "2026-11-04T06:00:00Z", "status": None if bad else 200, "body": None if bad else bodies[url], "error": "no response" if bad else None}
    return fetch, lambda path, jq: fetch(reg.GITHUB_API + path)

DAILY = {"acme": 10, "@acme/sdk": 90, "acme-ai": 20, "acme_sdk": 5}

def test_the_readme_install_line_names_the_primary_package_and_the_tracked_one_is_unchanged():
    p = bm.build([ACME], *_served(["npm install -g @acme/sdk@latest", "pip install -U 'acme-sdk[all]' acme-ai"], DAILY))["tools"][0]["packages"]
    assert p["npm"]["tracked"] == "acme" and p["npm"]["primary"] == "@acme/sdk" and p["npm"]["rule"] == "readme-install-line"
    assert p["npm"]["evidence"] == {"url": "https://raw.githubusercontent.com/acme/acme/HEAD/README.md", "fetched_at": "2026-11-04T06:00:00Z",
                                    "line": "npm install -g @acme/sdk@latest"}
    assert p["pypi"]["primary"] == "acme_sdk" and p["pypi"]["tracked"] == "acme-ai"         # acme-sdk and acme_sdk are one PyPI name
    assert [(c["package"], c["last7"]) for c in p["npm"]["candidates"]] == [("acme", 70), ("@acme/sdk", 630)]   # listed, never summed

def test_without_a_readme_line_the_most_downloaded_package_is_primary_only_when_every_one_was_observed():
    p = bm.build([ACME], *_served(["pip install something-else"], DAILY))["tools"][0]["packages"]
    assert (p["npm"]["primary"], p["npm"]["rule"]) == ("@acme/sdk", "highest-downloads") and (p["pypi"]["primary"], p["pypi"]["rule"]) == ("acme-ai", "highest-downloads")
    p = bm.build([ACME], *_served([], DAILY, failed={reg.PYPI_OVERALL.format(pkg="acme_sdk")}))["tools"][0]["packages"]
    assert p["pypi"]["primary"] is None and p["pypi"]["rule"] is None and "not observed for acme_sdk" in p["pypi"]["reason"]
    assert p["pypi"]["candidates"][1] == {"package": "acme_sdk", "url": reg.PYPI_OVERALL.format(pkg="acme_sdk"), "fetched_at": "2026-11-04T06:00:00Z",
                                          "last7": None, "reason": "pypistats API: no response"}

def test_siblings_and_history_never_change_the_7_day_figures():
    with_siblings = bm.build([ACME], *_served(["npm i @acme/sdk"], DAILY))["tools"][0]
    alone = bm.build([{k: v for k, v in ACME.items() if k != "siblings"}], *_served([], DAILY))["tools"][0]
    assert with_siblings["signals"] == alone["signals"] and with_siblings["weeks"] == alone["weeks"]
    assert with_siblings["signals"]["npm_7d"]["url"].endswith("/last-month/acme") and with_siblings["weeks"]["npm"]["package"] == "acme"
    with pytest.raises(ValueError, match="siblings"):
        bm.build([{**ACME, "npm": []}], *_served([], DAILY))                   # a sibling needs a tracked package in its registry

def test_install_lines_name_their_packages_and_skip_flags_versions_and_paths():
    assert reg.install_lines("Run `pip install foo` or\n$ npm i -g bar@1 | tee") == ["pip install foo", "npm i -g bar@1"]
    cases = {"npm i -g @opencode/cli@latest": ("npm", ["@opencode/cli"]), "npx -y firecrawl-cli@latest init --all": ("npm", ["firecrawl-cli"]),
             'pip install -U "autogen-agentchat" "autogen-ext[openai]"': ("pypi", ["autogen-agentchat", "autogen-ext"]),
             "pip install lm_eval[hf]": ("pypi", ["lm-eval"]), "uv pip install --prerelease=allow sglang": ("pypi", ["sglang"]),
             "pip install -e .": ("pypi", []), "pip install 'langsmith[aiohttp] @ git+ssh://git@github.com/x/y.git'": ("pypi", ["langsmith"]),
             "pip install kokoro>=0.9.4 soundfile": ("pypi", ["kokoro", "soundfile"]), 'npx",': (None, [])}
    assert {line: reg.installed(line) for line in cases} == cases

def test_a_readme_keeps_only_its_install_commands_and_every_fetch_goes_through_airstack_fetch(monkeypatch):
    pages = {"https://raw.githubusercontent.com/a/b/HEAD/README.md": (200, "# B\nA long README.\n```\npip install b-sdk\n```\n", {}),
             "https://api.npmjs.org/x": (200, '{"downloads": []}', {}), "https://api.npmjs.org/html": (200, "<html>", {}),
             "https://pypistats.org/closed": (0, "", {"x-robots": "disallowed"}), "https://api.npmjs.org/gone": (404, "", {})}
    monkeypatch.setattr(bm, "get", lambda url, headers=None: pages[url])
    e = {u: bm.envelope(u, now=lambda: "2026-11-05T00:00:00Z") for u in pages}
    readme = e["https://raw.githubusercontent.com/a/b/HEAD/README.md"]
    assert readme["body"] == {"install_lines": ["pip install b-sdk"]} and "not stored" in readme["projection"] and "long" not in json.dumps(readme)
    assert e["https://api.npmjs.org/x"]["body"] == {"downloads": []} and e["https://api.npmjs.org/html"]["error"] == "response was not JSON"
    assert "robots.txt" in e["https://pypistats.org/closed"]["error"] and e["https://api.npmjs.org/gone"]["error"] == "HTTP 404"
    assert bm.dead_hosts(e) == ["pypistats.org"]                              # every request to that host failed this run

def test_a_429_without_retry_after_is_retried_once_after_a_pause(monkeypatch):
    answers, slept = [(429, "", {}), (200, '{"ok": 1}', {})], []
    monkeypatch.setattr(bm, "get", lambda url, headers=None: answers.pop(0))
    assert bm.envelope("https://api.npmjs.org/x", sleep=slept.append)["body"] == {"ok": 1} and slept == [bm.BACKOFF]
    answers[:] = [(429, "", {}), (429, "", {}), (200, "{}", {})]
    assert bm.envelope("https://api.npmjs.org/x", sleep=slept.append)["error"] == "HTTP 429" and len(answers) == 1   # once, not forever

def test_a_run_where_a_host_was_unreachable_keeps_the_previous_run(monkeypatch, tmp_path):
    """An outage never blanks a source: the run is not saved and movers.json is rebuilt from the last good run."""
    raw, out, uni = tmp_path / "raw", tmp_path / "movers.json", tmp_path / "universe.json"
    uni.write_text(json.dumps([ACME]))
    monkeypatch.setattr(bm, "RAW", raw); monkeypatch.setattr(bm, "OUT", out); monkeypatch.setattr(bm, "UNIVERSE", uni); monkeypatch.setattr(bm, "ROOT", tmp_path)
    def recording(failed=()):
        saved = {}
        f, g = _served(["npm i acme"], DAILY, failed)
        def fetch(url):
            saved[url] = f(url); return saved[url]
        return lambda: (fetch, lambda path, jq: fetch(reg.GITHUB_API + path), saved)
    monkeypatch.setattr(bm, "recording", recording())
    raw.mkdir(); (raw / "0123.json").write_text("{}")                          # a per-URL file of the older format
    assert bm.main([]) == 0
    runs = list(raw.iterdir()); good = runs[0].read_bytes(); first = out.read_text()
    assert len(runs) == 1 and runs[0].name.endswith(".json.gz")              # the older files are gone; one run is the record
    monkeypatch.setattr(bm, "recording", recording(failed={reg.PYPI_OVERALL.format(pkg=p) for p in ("acme-ai", "acme_sdk")}))
    runs[0].rename(raw / "2000-01-01.json.gz")
    assert bm.main([]) == 0
    assert [p.name for p in raw.iterdir()] == ["2000-01-01.json.gz"] and (raw / "2000-01-01.json.gz").read_bytes() == good and out.read_text() == first

@pytest.mark.private_data
def test_every_tracked_package_has_its_weeks_and_its_primary_in_the_committed_data():
    universe = {t["id"]: t for t in json.loads(bm.UNIVERSE.read_text())}
    for t in json.loads(bm.OUT.read_text())["tools"]:
        u = universe[t["id"]]
        assert t["weeks"].keys() == {k for k in ("npm", "pypi") if u[k]} == t["packages"].keys(), t["id"]
        for k, w in t["weeks"].items():
            assert w["package"] == u[k][0] == t["packages"][k]["tracked"]
            assert w["series"] is None or len(w["series"]) == 26
            for x in w["series"] or []:
                assert (x["downloads"] is None) == (x["days"] == 0) and x["partial"] == (x["days"] < 7), (t["id"], x)
        for k, p in t["packages"].items():
            assert (p["rule"] == "only-package") == (not u.get("siblings", {}).get(k)), (t["id"], k)
            assert [c["package"] for c in p["candidates"]] == ([u[k][0]] + u["siblings"][k] if u.get("siblings", {}).get(k) else [])

@pytest.mark.private_data
def test_every_sibling_package_was_read_from_its_registry_in_the_committed_run():
    """AS-326's rule for registry ids holds for siblings: each one answered with its own download data, so none is a guess."""
    saved = json.loads(gzip.decompress(bm.latest_run(bm.RAW).read_bytes()))
    span = reg.weeks_span(json.loads(bm.OUT.read_text())["window"]["last7"][1])
    sibs = [(k, p) for t in json.loads(bm.UNIVERSE.read_text()) for k, ps in t.get("siblings", {}).items() for p in ps]
    assert sibs
    for k, p in sibs:
        e = saved[reg.NPM_RANGE.format(span=span, pkg=p) if k == "npm" else reg.PYPI_OVERALL.format(pkg=p)]
        assert e["status"] == 200 and not e["error"] and (e["body"].get("downloads") or e["body"].get("data")), (k, p)


# --- fetch: AirStack reads the web under one honest name, obeys robots.txt, and never requests a page robots.txt disallows. ---

def test_every_untrusted_xml_reader_refuses_dtds_entities_and_oversized_documents():
    for xml in (' ' * 5000 + '<!DOCTYPE r><r/>', '<!ENTITY x "secret"><r>&x;</r>', '<r>' + 'x' * fetch.MAX_BYTES + '</r>'):
        with pytest.raises(ET.ParseError):
            fetch.parse_xml(xml)
    assert fetch.parse_xml('<r><item>safe</item></r>').findtext('item') == 'safe'

class _Resp:
    def __init__(self, url, body, peer="93.184.216.34"): self.url, self.body, self.status, self.headers, self.peer = url, body.encode(), 200, {}, peer
    def read(self, n=-1): return self.body
    def geturl(self): return self.url
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False

def _web(monkeypatch, routes):
    seen = []
    def urlopen(req, timeout=0):
        seen.append((req.full_url, req.get_header("User-agent")))
        v = routes[req.full_url]
        if isinstance(v, int):
            raise urllib.error.HTTPError(req.full_url, v, "status", {}, None)
        return _Resp(req.full_url, v)
    fetch._robots.clear()
    monkeypatch.setattr(fetch, "_resolve", lambda *a, **k: [(fetch.socket.AF_INET, fetch.socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    monkeypatch.setattr(fetch, "_open", urlopen)
    return seen

def test_robots_txt_is_obeyed_and_a_disallowed_page_is_never_requested(monkeypatch):
    seen = _web(monkeypatch, {"https://a.test/robots.txt": "User-agent: AirStackBot\nDisallow: /private\n", "https://a.test/ok": "fine"})
    assert fetch.get("https://a.test/ok")[:2] == (200, "fine")
    assert fetch.get("https://a.test/private/x") == (0, "", {"x-robots": "disallowed"})
    assert "https://a.test/private/x" not in [u for u, _ in seen]
    assert all(ua == fetch.UA for _, ua in seen)                           # robots.txt and the page alike, under the honest name

def test_a_missing_robots_txt_allows_and_an_unreadable_one_closes_the_host(monkeypatch):
    _web(monkeypatch, {"https://b.test/robots.txt": 404, "https://b.test/p": "page", "https://c.test/robots.txt": 503})
    assert fetch.get("https://b.test/p")[0] == 200
    assert fetch.get("https://c.test/p") == (0, "", {"x-robots": "disallowed"})

def test_a_query_api_is_asked_by_post_under_the_same_name_and_the_same_robots_txt(monkeypatch):
    sent = []
    def urlopen(req, timeout=0):
        sent.append((req.full_url, req.get_method(), req.data, req.get_header("User-agent")))
        if req.full_url.endswith("/robots.txt"):
            return _Resp(req.full_url, "User-agent: *\nDisallow: /closed\n")
        return _Resp(req.full_url, '{"results": []}')
    fetch._robots.clear()
    monkeypatch.setattr(fetch, "_resolve", lambda *a, **k: [(fetch.socket.AF_INET, fetch.socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    monkeypatch.setattr(fetch, "_open", urlopen)
    assert fetch.get("https://q.test/v1/querybatch", data=b'{"queries": []}')[:2] == (200, '{"results": []}')
    assert sent[-1] == ("https://q.test/v1/querybatch", "POST", b'{"queries": []}', fetch.UA)
    assert fetch.get("https://q.test/closed", data=b"{}") == (0, "", {"x-robots": "disallowed"}) and sent[-1][0] != "https://q.test/closed"
    assert fetch.get("https://q.test/v1/x")[:1] == (200,) and sent[-1][1] == "GET"

def test_no_fetcher_pretends_to_be_a_browser():
    assert fetch.UA.startswith("AirStackBot/") and "airstack.bot" in fetch.UA
    code = [p for d in ("backend/airstack", "backend/tools", "tools") for p in (ROOT / d).rglob("*.py")]
    liars = [str(p.relative_to(ROOT)) for p in code if re.search(r"User-Agent\"?\s*[:=,]\s*\"Mozilla/", p.read_text())]
    assert not liars, liars

def test_fetch_refuses_private_local_and_redirected_destinations(monkeypatch):
    for address in ("file:///etc/passwd", "http://localhost/x", "http://127.0.0.1/x", "http://2130706433/x",
                    "http://[::1]/x", "http://169.254.169.254/latest/meta-data", "https://user:pass@example.com/"):
        assert fetch.get(address, robots=False) == (0, "", {"x-url": "unsafe"})
    monkeypatch.setattr(fetch, "_resolve", lambda name, *a, **k: [(fetch.socket.AF_INET, fetch.socket.SOCK_STREAM, 6, "", ("10.0.0.4" if name == "private.test" else "93.184.216.34", 443))])
    assert fetch.get("https://private.test/x", robots=False) == (0, "", {"x-url": "unsafe"})
    def redirected(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 302, "redirect", {"Location": "http://127.0.0.1/admin"}, None)
    monkeypatch.setattr(fetch, "_open", redirected)
    assert fetch.get("https://public.test/x", robots=False) == (0, "", {})

def test_fetch_checks_the_connected_peer_so_dns_rebinding_cannot_reach_a_private_service(monkeypatch):
    monkeypatch.setattr(fetch, "_resolve", lambda *a, **k: [(fetch.socket.AF_INET, fetch.socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])
    monkeypatch.setattr(fetch, "_open", lambda req, timeout: _Resp(req.full_url, "private response", peer="10.0.0.9"))
    assert fetch.get("https://rebinding.test/data", robots=False) == (0, "", {})
