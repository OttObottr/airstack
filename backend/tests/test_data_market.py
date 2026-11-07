# spec: AS-137 AS-140 AS-223 AS-232 AS-233 AS-263 AS-285 AS-327 AS-328
from conftest import *
import build_market, build_market_data as b, build_market_data as bmd, build_taxonomy as bt, json, pytest, re, refresh, reverify_corpus as rc, sqlite3
from airstack import paths
from airstack.budget import BudgetGuard, max_cost
from airstack.corpus import Corpus, check, failing_now, is_bad, norm, page_text
from airstack.publication import COMMENTARY_HOSTS, held_text, hold
from airstack.spark import FakeSpark, GuardedSpark, _SYSTEM
from airstack.store import ident


# --- market_corpus: The market corpus gate: a fact exists only if code found its words on the page; a paid input is never paid for twice. ---

PAGE = "<html><body><h1>Acme Notes</h1><p>Acme records Zoom, Google Meet and Microsoft Teams calls.</p>" \
       "<p>Supports 30+ languages. Available on iPhone and Android.</p><p>SOC 2 Type II and HIPAA compliant.</p>" + "<p>filler text</p>" * 80 + "</body></html>"

def fetcher(pages, log=None):
    def f(url, headers):
        if log is not None: log.append((url, dict(headers)))
        body = pages.get(url)
        if body is None: return 404, "", {}
        if headers.get("If-None-Match") == "v1": return 304, "", {}
        return 200, body, {"etag": "v1"}
    return f

def facts_for(payload):
    return {"facts": [
        {"metric": "x.joins_meeting_apps", "value_json": json.dumps(["Zoom", "Google Meet", "Webex"]), "quote": "Acme records Zoom, Google Meet and Microsoft Teams calls.", "source_ts": ""},
        {"metric": "x.compliance", "value_json": json.dumps(["SOC 2 Type II", "HIPAA"]), "quote": "SOC 2 Type II and HIPAA compliant.", "source_ts": ""},
        {"metric": "x.languages_count", "value_json": "30", "quote": "Supports 30+ languages.", "source_ts": ""},
        {"metric": "x.languages_count", "value_json": "100", "quote": "Supports 30+ languages.", "source_ts": ""},              # number not in its quote
        {"metric": "x.free_plan", "value_json": "true", "quote": "Free forever for everyone", "source_ts": ""},               # quote not on the page
    ]}

def setup(store, clock, pages, rec=None, day_cap="1"):
    fake = FakeSpark(rec or {"catalog": facts_for}, cost="0.01")
    corpus = Corpus(store)
    spark = GuardedSpark(fake, store, BudgetGuard(store, clock, job_cap="0.50", day_cap=day_cap, total_cap=day_cap, tool_calls=40), clock, memo=corpus)
    return fake, corpus, spark

def test_only_facts_whose_words_are_on_the_page_are_admitted(store, clock):
    pages = {"https://acme.test/": PAGE}
    fake, corpus, spark = setup(store, clock, pages)
    rep = build_market.run(spark, store, corpus, clock(), pages=[("fireflies", "home", "https://acme.test/")], fetch=fetcher(pages))
    assert rep["produced"] == 5 and rep["admitted"] == 3
    whys = {w for _, w in rep["rejected"]}
    assert "x.languages_count: the number is not in its quote" in whys and "x.free_plan: quote not found on the page" in whys
    apps = store.latest_fact("fireflies.x.joins_meeting_apps")
    assert apps.value == ["Google Meet", "Zoom"] and apps.source == "muse.catalog" and apps.url == "https://acme.test/"   # Webex isn't on the page: dropped
    prov = corpus.c.execute("SELECT call_ref, quote FROM fact_provenance WHERE fact_id=?", (apps.id,)).fetchone()
    assert prov[0].startswith("fake-") and "Microsoft Teams" in prov[1]

def test_a_second_run_costs_nothing_and_admits_nothing_new(store, clock):
    pages = {"https://acme.test/": PAGE}
    fake, corpus, spark = setup(store, clock, pages)
    p = [("fireflies", "home", "https://acme.test/")]
    build_market.run(spark, store, corpus, clock(), pages=p, fetch=fetcher(pages))
    n_calls, n_facts = fake.call_count, len(store.facts_for("fireflies"))
    rep = build_market.run(spark, store, corpus, clock(), pages=p, fetch=fetcher(pages))
    assert fake.call_count == n_calls and rep["calls"] == 0 and rep["cached"] == 1        # the memo answered: no model call, no reservation
    assert len(store.facts_for("fireflies")) == n_facts                                    # same facts, not duplicated
    assert corpus.c.execute("SELECT count(*) FROM verifications").fetchone()[0] == 5          # a replay re-checks, it doesn't re-count
    assert [r for r in store.calls() if r["kind"] == "cached"][0]["cost"] in ("0", 0)

def test_a_shell_or_missing_page_is_never_sent_to_the_model(store, clock):
    pages = {"https://shell.test/": "<html><body><div id=root></div><script>app()</script></body></html>"}
    fake, corpus, spark = setup(store, clock, pages)
    rep = build_market.run(spark, store, corpus, clock(), pages=[("otter", "home", "https://shell.test/"), ("otter", "pricing", "https://gone.test/")], fetch=fetcher(pages))
    assert fake.call_count == 0 and set(rep["shells"]) == {"https://shell.test/", "https://gone.test/"}

def test_a_refetch_is_conditional_and_a_304_reuses_the_stored_text(store, clock):
    pages, log = {"https://acme.test/": PAGE}, []
    corpus = Corpus(store)
    first = corpus.fetch("https://acme.test/", clock(), fetch=fetcher(pages, log))
    again = corpus.fetch("https://acme.test/", clock(), fetch=fetcher(pages, log))
    assert log[1][1].get("If-None-Match") == "v1" and again["cached"] and again["text"] == first["text"]

def test_the_batch_stops_at_its_cap_before_sending(store, clock):
    pages = {f"https://acme.test/{i}": PAGE.replace("Acme", f"Acme{i}") for i in range(10)}
    fake, corpus, spark = setup(store, clock, pages, day_cap="0.05")
    rep = build_market.run(spark, store, corpus, clock(), pages=[("fathom", "home", u) for u in pages], fetch=fetcher(pages))
    assert rep["stopped"] and rep["stopped"].startswith(("day_cap", "total_cap"))
    assert sum(float(r["spent"] or 0) for r in store.ledger()) <= 0.05

def test_values_are_checked_against_the_page_not_trusted():
    text = norm(page_text(PAGE))
    assert check({"metric": "x.devices", "value_json": '["iPhone", "Android", "Windows"]', "quote": "Available on iPhone and Android.", "source_ts": ""}, text)[2] == ["Android", "iPhone"]
    assert not check({"metric": "x.price", "value_json": "1", "quote": "Acme Notes", "source_ts": ""}, text)[0]          # outside the vocabulary
    assert not check({"metric": "x.store_users", "value_json": "true", "quote": "Supports 30+ languages.", "source_ts": ""}, text)[0]

def test_shapes_are_coerced_by_code_only_when_the_quote_still_holds():
    text = norm(page_text("<p>Rated 4.8 / 5</p><p>Cross-App Productivity: 100+ apps.</p>" + "<p>pad</p>" * 50))
    assert check({"metric": "x.store_rating", "value_json": '"4.8 / 5"', "quote": "Rated 4.8 / 5", "source_ts": ""}, text)[2] == {"rating": 4.8, "count": ""}
    assert check({"metric": "x.store_rating", "value_json": "4.9", "quote": "Rated 4.8 / 5", "source_ts": ""}, text)[0] is False
    assert check({"metric": "x.integrations", "value_json": "100", "quote": "Cross-App Productivity: 100+ apps.", "source_ts": ""}, text)[2] == ("x.integrations_count", 100)

def test_a_ratings_count_is_not_accepted_as_a_user_count():
    text = norm(page_text("<p>9 Ratings</p><p>Extension Communication 500,000 users</p>" + "<p>pad</p>" * 60))
    assert check({"metric": "x.store_users", "value_json": "9", "quote": "9 Ratings", "source_ts": ""}, text) == (False, "the quote does not say users", None)
    assert check({"metric": "x.store_users", "value_json": "500000", "quote": "Extension Communication 500,000 users", "source_ts": ""}, text)[0] is True

def test_a_wrong_shape_is_repaired_in_code_but_the_page_still_decides():
    text = norm(page_text("<p>SOC 2 Type II and HIPAA compliant.</p><p>Trusted by 11M + developers.</p><p>MIT license</p><p>Runs locally and self-hosted.</p>" + "<p>pad</p>" * 60))
    ok = lambda m, v, q: check({"metric": m, "value_json": v, "quote": q, "source_ts": ""}, text)
    assert ok("x.compliance", '"SOC 2 Type II"', "SOC 2 Type II")[2] == ["SOC 2 Type II"]            # a bare string becomes a one-item list
    assert ok("x.compliance", "SOC 2 Type II, HIPAA", "SOC 2 Type II and HIPAA compliant.")[2] == ["HIPAA", "SOC 2 Type II"]   # an unquoted "A, B": split, each checked
    assert ok("x.compliance", '"ISO 27001"', "SOC 2 Type II")[0] is False                           # a name that is not on the page is dropped
    assert ok("x.compliance", "true", "SOC 2 Type II")[0] is False                                    # no names to check: still rejected
    assert ok("x.customers_claimed", "11000000", "Trusted by 11M + developers.")[2] == "Trusted by 11M + developers."   # the value is the page's own words
    assert ok("x.license", "MIT", "MIT license")[2] == "MIT license"
    assert ok("x.deployment", "self-hosted", "Runs locally and self-hosted.")[2] == ["self-hosted"]
    assert ok("x.open_source", "true", "MIT license")[2] is True
    assert ok("x.license", "MIT", "Apache 2.0 license")[0] is False                                   # a quote that is not on the page never passes

def test_a_page_that_ships_its_text_as_one_long_line_still_fits_the_envelope():
    """A minified single-line page is split within the request envelope."""
    from airstack.corpus import chunks, CHUNK_CHARS
    parts = chunks("x" * (CHUNK_CHARS * 2 + 10))
    assert parts and all(len(p) <= CHUNK_CHARS + 1 for p in parts)
    assert chunks("a\nb\n") == ["a\nb\n"]                                           # short pages chunk exactly as before (memo keys unchanged)


# --- market_data: The market the page shows, built from the committed corpus (data/airstack-market.db): no model call, no price, every cell sourced. ---

@pytest.mark.private_data
def test_every_shown_value_has_its_pages_and_no_price_reaches_the_screen():
    F, names, fleet = bmd.load()
    vendors = [bmd.vendor(e, F, names) for e in bmd.INCUMBENTS if e in F]
    assert len(vendors) == 5
    for v in vendors:
        for k, c in v.items():
            if isinstance(c, dict) and "value" in c:
                assert c["sources"] and all(s["url"].startswith("https://") and s["checked"] for s in c["sources"]), (v["name"], k)
    assert not bmd.CURRENCY.search(json.dumps([[v["what"]["value"]] for v in vendors if v["what"]]))
    assert not bmd.CURRENCY.search(json.dumps(bmd.platform_rules(F)))

@pytest.mark.private_data
def test_platform_answers_rest_on_verified_quotes_or_say_unknown():
    F, _, _ = bmd.load()
    R = bmd.platform_rules(F)
    assert R["Microsoft"]["Teams Premium"]["online"]["status"] == "covered"
    assert "must assign a Teams Premium license" in R["Microsoft"]["Teams Premium"]["online"]["source"]["quote"]
    assert R["Microsoft"]["Teams without Premium"]["online"]["status"] == "unmet"
    assert R["Microsoft"]["Teams Premium"]["in_person"]["status"] == "unknown" and R["Microsoft"]["Teams Premium"]["in_person"]["source"] is None
    assert R["Zoom"]["Zoom Workplace paid plan"]["online"]["status"] == "covered"
    assert R["Zoom"]["Zoom Workplace Basic"]["online"]["status"] == "limited"
    for fam in R.values():
        for plan in fam.values():
            for rule in plan.values():
                assert rule["status"] == "unknown" or rule["source"]["call"].startswith("resp_")   # every known answer cites a real Muse extraction

@pytest.mark.private_data
def test_the_corpus_counts_each_claim_once_and_its_pass_rate_is_published():
    _, _, fleet = bmd.load()
    assert fleet["calls"] >= 41 and fleet["checked"] >= fleet["passed"] > 0
    assert not ({"credits", "model"} & fleet.keys())
    assert fleet["passed"] / fleet["checked"] >= 0.9

def test_a_plan_named_with_and_without_the_word_plan_is_one_plan():
    """Notion's pages say 'Free' and 'Free Plan': one plan, shown once."""
    import build_market_data as b
    F = {"x": {"x.plan_names": [{"value": ["Free", "Plus Plan"], "kind": "pricing", "url": "https://x.example/pricing", "checked": "2026-11-04", "quote": "q", "call": "c1"},
                                {"value": ["Free Plan", "Plus", "Business"], "kind": "home", "url": "https://x.example/", "checked": "2026-11-04", "quote": "q", "call": "c2"}]}}
    assert [v.lower() for v in b.profile("x", F)["plan_names"]["value"]] == ["free", "plus", "business"]


# --- projection_rules: A quote proves the words are on the page, not what they mean. Golden cases from the review: each reads the way a person would. ---

def fact(quote, value, kind="home", url="https://vendor.example/"):
    return {"quote": quote, "value": value, "kind": kind, "url": url, "checked": "2026-11-04", "call": "c1"}

def prof(e, F):
    b.HIDDEN.clear(); return b.profile(e, {e: F}) or {}                   # nothing left to show: no profile at all

def test_a_download_button_for_the_readers_system_is_not_the_products_platform_list():
    p = prof("cursor", {"x.platforms": [fact("Download for macOS \u2913", ["macOS"])]})
    assert "platforms" not in p and b.HIDDEN["platforms"]

def test_sdk_languages_show_only_for_published_packages_never_from_an_ides_navigation():
    b.SDK_SCOPE.clear()
    assert "sdk_languages" not in prof("cursor", {"x.sdk_languages": [fact("SDK TypeScript Python Bridge", ["TypeScript", "Python"], "docs")]})
    b.SDK_SCOPE.add("openai-sdk")
    assert prof("openai-sdk", {"x.sdk_languages": [fact("Python and TypeScript SDKs", ["Python", "TypeScript"], "docs")]})["sdk_languages"]["value"] == ["Python", "TypeScript"]
    b.SDK_SCOPE.clear()

def test_models_are_models_not_vendors_footnotes_or_the_product_itself():
    p = prof("cursor", {"x.models_supported": [
        fact("Composer 2.5, GPT-5.6 Sol, Grok 4.7, Anthropic, Cursor, OpenAI, Grok models", ["Composer 2.5", "GPT-5.6 Sol", "Grok 4.7", "Anthropic", "Cursor", "OpenAI", "Grok models"]),
        fact("*Only Grok models are available on this plan", ["Grok"], "pricing")]})
    assert p["models_supported"]["value"] == ["Composer 2.5", "GPT-5.6 Sol", "Grok 4.7"]

def test_a_trial_or_credits_never_reads_as_a_free_plan_and_a_contrary_page_leaves_it_unknown():
    assert "free_plan" not in prof("articulate-360", {"x.free_plan": [fact("Start your free 30-day trial", True)]})
    assert "free_plan" not in prof("sketch", {"x.free_plan": [fact("Get started for free", True), fact("Sketch has no free plan", False, "pricing")]})
    assert prof("notion", {"x.free_plan": [fact("Free for individuals", True, "pricing")]})["free_plan"]["value"] is True

def test_a_certification_in_progress_is_not_held():
    p = prof("limesurvey", {"x.compliance": [fact("ISO 27001 is in progress", ["ISO 27001"], "security"), fact("We are SOC 2 Type II compliant", ["SOC 2"], "security")]})
    assert p["compliance"]["value"] == ["SOC 2"]

def test_a_product_launch_is_not_a_company_founding():
    assert "founded_year" not in prof("x", {"x.founded_year": [fact("Launched in 2019", 2019)]})
    assert prof("y", {"x.founded_year": [fact("Founded in 2015 in Berlin", 2015)]})["founded_year"]["value"] == 2015


# --- extraction_rules: Extraction rules, with the real quotes that fooled the pipeline as fixtures. A quote being ON the page is not the same as the quote SUPPORTING the claim. ---

def admitted(metric, value, quote):
    return check({"metric": metric, "value_json": json.dumps(value), "quote": quote}, norm(quote))[0]

FREE_PLANS = ["Start free on cloud", "Free to get started. Flexibility at scale.", "Everything in Free, plus:", "Free: 1,000 credits every month, 10 a minute, 2 at a time.",
              "Start for free No credit card required", "Free, no credit card required", "Forever $0 /mo", "Starter\nFor everyone\n$0 / month", "Start With Kilo Auto Free - No Credit Card required"]

NOT_FREE_PLANS = ["Yes. You can create an account and start transcribing immediately with no credit card required.",     # AssemblyAI: no card is not a free plan
                  "Start with 5,000 free credits.", "Free $200 credit then pay-as-you-go", "Start free trial No credit card required",
                  "Start free with trial credits — no card required.", "Free credits $ 1 once per person.", "Start for free with $30 of credits, and pay only for what your agents run.",
                  "Pay as you go\n$0\nPay per token for every cloud model.", "Limited My Notes features included with Workplace Basic."]

@pytest.mark.parametrize("quote", FREE_PLANS)
def test_a_free_plan_is_admitted_when_the_quote_says_free_or_zero_a_month(quote):
    assert admitted("x.free_plan", True, quote)

@pytest.mark.parametrize("quote", NOT_FREE_PLANS)
def test_a_trial_one_time_credits_or_pay_as_you_go_is_not_a_free_plan(quote):
    assert not admitted("x.free_plan", True, quote)

def test_a_ratings_count_is_not_a_user_count_and_a_code_fragment_is_not_a_description():
    assert not admitted("x.store_users", 9, "9 Ratings") and admitted("x.store_users", 1000, "1,000 users")
    assert not admitted("x.what_it_does", "x", 'await client.textToSpeech.convert( "JBFqnCBsd6RMkjVDRZzb" , {')
    assert admitted("x.what_it_does", "x", "tl;dv is an AI-powered notetaker that goes beyond simple recording.") and admitted("x.what_it_does", "x", "Run LLMs with MLX")

def test_claims_admitted_under_older_rules_are_found_by_replay_and_never_counted(tmp_path):
    db = sqlite3.connect(tmp_path / "m.db")
    db.executescript("CREATE TABLE raw_items(url TEXT, text TEXT); CREATE TABLE verifications(url TEXT, metric TEXT, value_json TEXT, quote TEXT, ok INT);")
    db.execute("INSERT INTO raw_items VALUES('https://store/app', 'Fathom 9 Ratings 4.8'), ('https://v/pricing', 'Start free on cloud')")
    db.execute("INSERT INTO verifications VALUES('https://store/app','x.store_users','9','9 Ratings',1), ('https://v/pricing','x.free_plan','true','Start free on cloud',1)")
    bad = failing_now(db)
    assert bad == {("https://store/app", "9 Ratings", "x.store_users")} and is_bad(bad, "https://store/app", "9 Ratings", "x.store_users") and not is_bad(bad, "https://v/pricing", "Start free on cloud", "x.free_plan")

def test_a_description_is_taken_from_the_homepage_or_docs_before_a_pricing_page():
    import build_market_data as b
    r = b.DESCRIPTION_RANK
    assert r["home"] < r["docs"] < r["pricing"] and b.KIND_RANK["docs"] < 9

@pytest.mark.private_data
@pytest.mark.skipif((paths.DATA / "PUBLISHED.md").exists(), reason="the published snapshot has no page text to replay the rules over")
def test_no_public_file_shows_a_claim_that_todays_rules_reject():
    """The page's numbers, the evidence chain and the profiles skip what replay rejects; the headline says how many were withheld."""
    bad = failing_now(sqlite3.connect(f"file:{paths.MARKET_DB}?mode=ro", uri=True))
    assert bad, "the stored corpus still holds claims admitted under older rules (the fixtures above are real)"
    chain = json.loads(paths.CHAIN_DATA.read_text())
    shown = {(f["url"], f["quote"], f["metric"]) for e in chain["entities"].values() for f in e["facts"]}
    assert not [b for b in bad if b in shown or (b[0], b[1], b[2].replace("x.integrations", "x.integrations_count")) in shown]
    js = paths.MARKET_DATA.read_text(); fleet = json.loads(js[js.index("{"):js.rindex("}") + 1])["fleet"]
    assert fleet["withheld"] == len(bad) and fleet["passed"] <= fleet["checked"]


# --- taxonomy: The taxonomy: every node is defined and hangs from a department; every listed product is placed once or counted as unplaced, never ---

TAX, XW = json.loads(bt.TAXONOMY.read_text()), json.loads(bt.CROSSWALK.read_text())

D = json.loads(paths.DIRECTORY.read_text())

CATALOG, UNIVERSE = json.loads(paths.CATALOG.read_text()), json.loads(paths.UNIVERSE.read_text())

P = json.loads(paths.PROFILES.read_text())

IDX = json.loads(bt.OUT.read_text())

PARENT, ANC, DEPT = bt.tree(TAX)

def test_every_node_has_a_definition_examples_and_a_parent_chain_to_a_department():
    ids, names = [n["id"] for n in TAX["nodes"]], [n["name"].lower() for n in TAX["nodes"]]
    assert len(set(ids)) == len(ids) and len(set(names)) == len(names)
    depts = [n for n in TAX["nodes"] if n["parent"] is None]
    assert 15 <= len(depts) <= 16 and 150 <= len(ids) - len(depts) <= 250
    for n in TAX["nodes"]:
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", n["id"]), n["id"]
        assert n["definition"].endswith(".") and n["definition"].count(". ") == 0 and len(n["definition"]) <= 200, n["id"]   # one sentence
        assert n["includes"].strip() and 2 <= len(n["examples"]) <= 4, n["id"]
        seen, x = set(), n["id"]
        while PARENT[x]:                                                    # the chain ends at a department, without a loop
            assert x not in seen and PARENT[x] in PARENT, n["id"]
            seen.add(x); x = PARENT[x]
        assert x in {d["id"] for d in depts}

def test_every_catalog_category_registry_lane_and_curated_product_points_at_a_real_node():
    assert set(XW["catalog"]) == {e["category"] for e in CATALOG}            # a category may map to nothing (a vendor collection), but never be missing
    assert set(XW["lanes"]) == {e["lane"] for e in UNIVERSE}
    assert all(v["node"] in PARENT or (v["node"] is None and v["relation"] == "collection") for v in XW["catalog"].values())
    assert all(v in PARENT for v in XW["lanes"].values())
    known = {e["id"] for e in CATALOG + UNIVERSE}
    for pid, v in XW["products"].items():
        nodes = [v] if isinstance(v, str) else v["nodes"]
        assert pid in known and nodes and all(n in PARENT for n in nodes), pid
        assert isinstance(v, str) or v["why"].strip(), pid

def test_crosswalk_types_are_directory_types_under_their_own_labels():
    label = {t[0]: t[1] for t in D["types"]}
    for q, (name, node, how, *why) in XW["types"].items():
        assert label.get(q) == name, q                                        # a mistyped id would carry another type's label
        assert (node in PARENT and how in ("equivalent", "narrower", "overlapping")) or (node is None and how in ("generic", "excluded")), q
        assert how != "excluded" or why, q

@pytest.mark.private_data
def test_the_index_is_rebuilt_byte_for_byte(tmp_path, monkeypatch):
    monkeypatch.setattr(bt, "OUT", tmp_path / "taxonomy-index.json")
    bt.write(bt.build())
    assert (tmp_path / "taxonomy-index.json").read_bytes() == paths.TAXONOMY_INDEX.read_bytes()

def test_every_listed_product_is_placed_or_counted_unplaced_and_the_counts_add_up():
    every = [p[0] for p in D["products"]] + [e["id"] for e in CATALOG + UNIVERSE]
    placed, unplaced = set(IDX["products"]), [x for v in IDX["unplaced"].values() for x in v]
    assert len(unplaced) == len(set(unplaced)) and not placed & set(unplaced) and placed | set(unplaced) == set(every)
    s = IDX["summary"]
    assert s["products"] == len(every) and s["placed"] == len(placed) and s["unplaced"] == {k: len(v) for k, v in IDX["unplaced"].items()}
    assert s["in_a_category"] + s["department_only"] == s["placed"]
    assert s["directory"]["placed"] + s["directory"]["unplaced"] == len(D["products"]) == s["directory"]["listed"]
    members = {n: set() for n in PARENT}
    for pid, nodes in IDX["products"].items():
        for n, _ in nodes:
            for x in [n] + ANC[n]:
                members[x].add(pid)
    for n, v in IDX["nodes"].items():
        assert v["listed"] == len(members[n]) and v["researched"] == len(members[n] & set(P)), n
        assert set(v["top"]) <= members[n] and len(v["top"]) == min(24, len(members[n])), n
    extra = sum(len({DEPT[n] for n, _ in nodes}) - 1 for nodes in IDX["products"].values())
    assert sum(IDX["nodes"][d]["listed"] for d in PARENT if PARENT[d] is None) == len(placed) + extra   # a product in two departments counts in both, and only then
    assert s["unplaced"]["generic"] > 0 and s["by_muse"] == 0 and IDX["source"]["muse"] == "no product is placed by a model"   # counted, not hidden

def test_a_nodes_best_known_products_come_first_and_unknown_documentation_comes_last():
    links = {p[0]: p[6] for p in D["products"]}
    for n, v in IDX["nodes"].items():
        known = [links[x] for x in v["top"] if x in links]
        assert known == sorted(known, reverse=True), n

def test_no_product_is_in_two_departments_without_a_reason():
    for pid, nodes in IDX["products"].items():
        if len({DEPT[n] for n, _ in nodes}) > 1:
            assert isinstance(XW["products"].get(pid), dict) and XW["products"][pid]["why"], pid

def test_an_example_that_is_listed_is_placed_under_the_node_that_names_it():
    by_name = {bt.key(p[1]): p[0] for p in D["products"]} | {bt.key(e["name"]): e["id"] for e in CATALOG + UNIVERSE}
    wrong = []
    for n in TAX["nodes"]:
        for ex in n["examples"]:
            pid = by_name.get(bt.key(ex))
            if pid in IDX["products"] and not any(x == n["id"] or n["id"] in ANC[x] for x, _ in IDX["products"][pid]):
                wrong.append((n["id"], ex, IDX["products"][pid]))
    assert not wrong                                                          # an example listed but unplaced (a generic Wikidata type) is allowed

def test_the_ambiguity_set_is_scored_and_every_case_lands_where_it_should():
    cases = json.loads((paths.TAXONOMY_GOLDEN).read_text())["cases"]
    tix = {t[0]: i for i, t in enumerate(D["types"])}
    misses = []
    for c in cases:
        if "type" in c:
            node, _, _ = bt.type_node(tix[c["type"]], D["types"], XW["types"], ANC)
            got = [node] if node else None
        else:
            got = sorted(n for n, _ in IDX["products"][c["product"]]) if c["product"] in IDX["products"] else None
        if got != (sorted(c["expect"]) if c["expect"] else None):
            misses.append((c.get("type") or c["product"], c["expect"], got))
    print(f"ambiguity set: {len(cases) - len(misses)} of {len(cases)}")
    assert len(cases) >= 40 and not misses

def test_the_walk_takes_the_nearest_listed_type_stops_at_generic_ones_and_never_picks_between_branches():
    T = [["Q0", "software", [], 0, 0], ["Q1", "free software", [0], 0, 0], ["Q2", "graphics", [0], 0, 0], ["Q3", "photo", [2], 0, 0],
         ["Q4", "tool", [3, 1], 0, 0], ["Q5", "audio", [0], 0, 0], ["Q6", "both", [3, 5], 0, 0], ["Q7", "lonely", [1], 0, 0], ["Q8", "deep", [4], 0, 0]]
    xw = {"Q0": ["software", None, "generic"], "Q1": ["free software", None, "generic"], "Q2": ["graphics", "design", "narrower"],
          "Q3": ["photo", "photo-editing", "narrower"], "Q5": ["audio", "audio-production", "narrower"]}
    assert bt.type_node(3, T, xw, ANC)[:2] == ("photo-editing", "Q3")                                 # listed: itself
    assert bt.type_node(8, T, xw, ANC)[:2] == ("photo-editing", "Q3")                                 # unlisted: the nearest listed type above, past a generic one
    assert bt.type_node(7, T, xw, ANC)[:2] == (None, "unmapped")                                      # only generic types above: nothing
    assert bt.type_node(1, T, xw, ANC)[:2] == (None, "generic")
    assert bt.type_node(6, T, xw, ANC) == (None, "ambiguous", ["audio-production", "photo-editing"])  # two branches: unplaced, both named
    xw["Q6"] = ["both", "design", "narrower"]; T[6][2] = [2, 3]
    assert bt.type_node(6, T, xw, ANC)[0] == "design"                                                 # listed itself
    del xw["Q6"]
    assert bt.type_node(6, T, xw, ANC)[0] == "photo-editing"                                          # a department and its category: the category

# ---- the Muse placement stage, with a fake model ----
ITEMS = [{"id": "Q1", "name": "Acme Notes", "description": "Acme Notes is a note-taking app that syncs across your devices.", "url": "https://acme.test/"},
         {"id": "Q2", "name": "Bolt", "description": "The fastest way to ship.", "url": "https://bolt.test/"},
         {"id": "Q3", "name": "Cobalt", "description": "Cobalt is a help desk for support teams.", "url": "https://cobalt.test/"},
         {"id": "Q4", "name": "Dune", "description": "Dune turns spreadsheets into dashboards.", "url": "https://dune.test/"},
         {"id": "Q5", "name": "Ember", "description": "Ember is a CRM for small teams.", "url": "https://ember.test/"}]

ANSWERS = {"Acme Notes": {"node": "notes", "quote": "a note-taking app"},
           "Bolt": {"node": "", "quote": ""},                                                     # says nothing about the job: abstains
           "Cobalt": {"node": "help-desk", "quote": "the best help desk on the market"},          # quote not in the description
           "Dune": {"node": "dashboards", "quote": "turns spreadsheets into dashboards"},          # not a category in the list
           "Ember": {"node": "sales", "quote": "a CRM for small teams"}}                           # a department, not a category

def stage(store, clock, cap="1"):
    fake = FakeSpark({"place": lambda p: ANSWERS[p["product"]]}, cost="0.001")
    corpus = Corpus(store)
    return fake, corpus, GuardedSpark(fake, store, BudgetGuard(store, clock, job_cap="0.10", day_cap=cap, total_cap=cap, tool_calls=2, tool_searches=0), clock, memo=corpus)

def test_a_muse_placement_is_kept_only_with_a_quote_from_the_products_own_description(store, clock):
    fake, corpus, spark = stage(store, clock)
    rep = bt.place(spark, corpus, ITEMS, bt.menu(TAX), live=True)
    assert rep["placed"] == {"Q1": {"node": "notes", "quote": "a note-taking app", "source": "https://acme.test/", "call_ref": "fake-1"}}
    assert rep["abstained"] == ["Q2"]
    assert rep["rejected"] == {"Q3": "quote not in the product's description", "Q4": "not a category in the list", "Q5": "not a category in the list"}
    assert fake.call_count == 5 and all(set(p) == {"product", "description", "categories"} for _, _, p in fake.calls)

def test_muse_is_never_called_without_live_and_a_rerun_replays_from_the_memo_for_nothing(store, clock):
    fake, corpus, spark = stage(store, clock)
    rep = bt.place(spark, corpus, ITEMS, bt.menu(TAX), live=False)
    assert fake.call_count == 0 and rep["not_run"] == 5 and not rep["placed"]
    first = bt.place(spark, corpus, ITEMS, bt.menu(TAX), live=True, limit=2)                           # --limit caps new paid calls only
    assert fake.call_count == 2 and first["calls"] == 2 and first["not_run"] == 3
    again = bt.place(spark, corpus, ITEMS, bt.menu(TAX), live=False)
    assert fake.call_count == 2 and again["replayed"] == 2 and again["placed"] == first["placed"] and again["abstained"] == first["abstained"]
    assert all(r["cost"] == "0" for r in store.calls(limit=100) if r["kind"] == "cached")

def test_with_no_cap_set_a_live_run_is_refused_before_anything_is_sent(store, clock):
    fake, corpus, spark = stage(store, clock, cap="0")
    rep = bt.place(spark, corpus, ITEMS, bt.menu(TAX), live=True)
    assert fake.call_count == 0 and rep["stopped"] and not rep["placed"]

def test_the_whole_category_list_fits_in_one_call_and_departments_are_not_offered():
    choices = bt.menu(TAX)
    assert {c[0] for c in choices} == {n["id"] for n in TAX["nodes"] if n["parent"]}
    long = dict(ITEMS[0], description="x" * 400)
    max_cost("place", bt.payload(long, choices), _SYSTEM["place"])          # raises if the request is larger than a call may be

def test_only_researched_products_whose_type_names_no_job_are_sent_to_muse():
    items = bt.candidates(IDX, D, P)
    want = set(IDX["unplaced"]["generic"]) | set(IDX["unplaced"]["unmapped"])
    assert items and all(i["id"] in want and i["id"] in P and i["description"] for i in items)
    assert not {i["id"] for i in items} & set(IDX["products"])
    print(f"Muse placement candidates: {len(items):,} researched directory products with a generic or unmapped type")

def test_a_muse_placement_applies_only_to_products_the_types_left_unplaced(tmp_path, monkeypatch):
    generic, typed = IDX["unplaced"]["generic"][0], next(p for p, v in IDX["products"].items() if v[0][1].startswith("Q"))
    idx = bt.build({generic: {"node": "notes"}, typed: {"node": "notes"}, IDX["unplaced"]["excluded"][0]: {"node": "notes"}})
    assert idx["products"][generic] == [["notes", "muse"]] and idx["summary"]["by_muse"] == 1
    assert idx["products"][typed] == IDX["products"][typed] and IDX["unplaced"]["excluded"][0] in idx["unplaced"]["excluded"]


# --- reverify: The re-check link of the chain of custody: unchanged, changed-but-still-supported, changed-and-unsupported, and failed. Fake network only. ---

BODY = "<html><body><p>Acme records Zoom and Google Meet calls.</p>" + "<p>filler text here</p>" * 60 + "</body></html>"

def seed(store, url="https://acme.test/", body=BODY, etag="v1"):
    corpus = Corpus(store)
    import hashlib
    corpus.c.execute("INSERT INTO raw_items(url,status,fetched_at,etag,last_modified,body_hash,text,kind) VALUES(?,?,?,?,?,?,?,?)",
                     (url, 200, T0, etag, None, hashlib.sha256(body.encode()).hexdigest(), "stored text", "home"))
    f = store.append_fact(entity_id="acme", metric="x.joins_meeting_apps", value=["Zoom"], source="muse.catalog", url=url, source_ts=None, observed_at=T0)
    corpus.c.execute("INSERT INTO fact_provenance(fact_id, call_ref, quote, page_kind) VALUES(?,?,?,?)", (f.id, "resp_x", "Acme records Zoom and Google Meet calls.", "home"))
    return corpus

def test_a_304_means_unchanged_and_nothing_is_overwritten(store, clock):
    corpus = seed(store)
    res = rc.run(corpus, T_EVENT, fetch=lambda u, h: (304, "", {}) if h.get("If-None-Match") == "v1" else (200, BODY, {}))
    assert res[0]["outcome"] == "unchanged" and res[0]["status"] == 304
    assert corpus.c.execute("SELECT text FROM raw_items").fetchone()[0] == "stored text"          # the stored page text is never replaced
    assert tuple(corpus.c.execute("SELECT outcome, quotes_ok, quotes_total FROM rechecks").fetchone()) == ("unchanged", 1, 1)

def test_a_changed_page_that_still_says_it_is_recorded_as_such():
    store = Store(); corpus = seed(store)
    res = rc.run(corpus, T_EVENT, fetch=lambda u, h: (200, BODY.replace("filler", "other"), {}))
    assert res[0]["outcome"] == "changed_quotes_present" and "still on it" in res[0]["note"]

def test_a_changed_page_that_no_longer_says_it_is_flagged_and_check_mode_fails():
    store = Store(); corpus = seed(store)
    res = rc.run(corpus, T_EVENT, fetch=lambda u, h: (200, "<html><body>" + "<p>Totally different page.</p>" * 40 + "</body></html>", {}))
    assert res[0]["outcome"] == "changed_quotes_missing" and res[0]["quotes_ok"] == 0
    assert rc.summary(res)["changed_quotes_missing"] == 1

def test_a_failed_fetch_is_a_failure_never_a_pass():
    store = Store(); corpus = seed(store)
    res = rc.run(corpus, T_EVENT, fetch=lambda u, h: (503, "", {}))
    assert res[0]["outcome"] == "fetch_failed" and res[0]["quotes_ok"] is None and "nothing was re-checked" in res[0]["note"]
    assert corpus.c.execute("SELECT count(*) FROM rechecks WHERE outcome='unchanged'").fetchone()[0] == 0

def test_an_identical_200_is_unchanged_without_a_304():
    store = Store(); corpus = seed(store, etag=None)
    assert rc.run(corpus, T_EVENT, fetch=lambda u, h: (200, BODY, {}))[0]["outcome"] == "unchanged"

def test_rechecks_are_append_only_history_one_row_per_run():
    store = Store(); corpus = seed(store)
    rc.run(corpus, T0, fetch=lambda u, h: (304, "", {})); rc.run(corpus, T_EVENT, fetch=lambda u, h: (503, "", {}))
    assert [r[0] for r in corpus.c.execute("SELECT outcome FROM rechecks ORDER BY id")] == ["unchanged", "fetch_failed"]


# --- refresh: The freshness scheduler learns each page's interval from its own history and publishes ages, never spend. ---

def test_a_page_that_changed_is_checked_sooner_and_a_quiet_page_later_within_bounds():
    assert refresh.interval(14, []) == 14
    assert refresh.interval(14, ["unchanged", "changed_quotes_present"]) == 7
    assert refresh.interval(14, ["changed_quotes_missing", "unchanged", "unchanged"]) == 28
    assert refresh.interval(14, ["unchanged"] * 9) == 56                  # never more than four times the base

@pytest.mark.private_data
def test_every_page_behind_a_fact_or_a_price_is_planned_and_the_public_file_has_no_money():
    rows, _ = refresh.plan()
    assert len(rows) > 5000 and {r["tier"] for r in rows} <= set(refresh.TIERS)
    assert all(r["quotes"] for r in rows)                                 # a page is re-checked against the quotes it backs
    f = refresh.freshness(rows)
    assert set(f) <= set(refresh.TIERS) and "$" not in json.dumps(f) and "cost" not in json.dumps(f)


# --- publication: The publication hold: a third-party review never becomes a citation, a source or AirStack's own words. Stored records stay intact. ---

REVIEW = "https://javisreview.com/review/fireflies-ai-review-2026/"

GOOD = "https://workspaceupdates.googleblog.com/2026/08/post.html"

def sample():
    return {"verdicts": [{"reason": "Covered on Android. Fireflies review additionally flags credit limits and biometric consent risk. This seat still needs a note-taker.",
                          "stored_reason": None, "evidence": [{"ref": "f3", "url": GOOD}, {"ref": "f10", "fact": "A review", "url": REVIEW}],
                          "judge": {"citations": ["f3", "f10"], "confidence": 0.9}}],
            "searched": [{"title": "Google post", "url": GOOD}, {"title": "Fireflies Review: Voiceprint Lawsuits", "url": REVIEW}],
            "urls": [GOOD, REVIEW], "pricing": {"note": "AI credit limits apply on the free plan"}, "nothing": None}

def test_commentary_sources_and_the_citations_that_point_at_them_are_dropped():
    out = hold(sample()); text = json.dumps(out)
    assert "javisreview" not in text and "Voiceprint" not in text
    assert [e["ref"] for e in out["verdicts"][0]["evidence"]] == ["f3"] and out["verdicts"][0]["judge"]["citations"] == ["f3"]
    assert out["urls"] == [GOOD] and [s["url"] for s in out["searched"]] == [GOOD]

def test_an_allegation_sentence_is_removed_from_prose_only_and_the_rest_of_the_reason_stays():
    r = hold(sample())["verdicts"][0]["reason"]
    assert r == "Covered on Android. This team still needs a note-taker." and "biometric" not in r

def test_a_legitimate_fact_that_mentions_credit_limits_is_untouched_and_nulls_stay_null():
    out = hold(sample())
    assert out["pricing"]["note"] == "AI credit limits apply on the free plan" and out["nothing"] is None and out["verdicts"][0]["stored_reason"] is None

def test_the_hold_is_idempotent_and_does_not_alter_its_input():
    s = sample(); before = json.dumps(s); once = hold(s)
    assert json.dumps(s) == before and hold(once) == once

@pytest.mark.private_data
def test_no_generated_public_file_carries_withheld_content():
    """Release gate for the generated page, evidence chain and market data."""
    for f in (paths.SITE_DATA, paths.CHAIN_DATA, paths.MARKET_DATA):
        assert not held_text(f.read_text()), f.name
    assert COMMENTARY_HOSTS

def test_only_the_vendor_the_platform_maker_a_store_a_registry_or_a_regulator_or_court_is_citable():
    """AS-232: the classes a verdict may rest on. A review, the press and an unknown domain are none of them: unknown is never citable."""
    from airstack.publication import source_class, uncitable
    assert source_class("https://www.fireflies.ai/pricing", {"fireflies.ai"}) == source_class("https://app.fireflies.ai/x", {"fireflies.ai"}) == "vendor"
    assert source_class("https://fireflies.ai/pricing") is None and source_class(None) is None
    assert source_class(GOOD) == source_class("https://support.google.com/meet/answer/1") == "maker"
    assert source_class("https://apps.apple.com/app/id1") == source_class("https://play.google.com/store/apps/details?id=x") == "store"
    assert source_class("https://registry.npmjs.org/x") == source_class("https://pypi.org/project/x/") == source_class("https://api.npmjs.org/downloads/x") == "registry"
    assert source_class("https://www.ftc.gov/news") == source_class("https://ilnd.uscourts.gov/x") == "regulator or court"
    assert source_class(REVIEW) is None and source_class("https://9to5google.com/x") is None and source_class("https://notgov.com/x") is None
    ev = [{"ref": "f3", "key": "meet.in_person_notes", "url": GOOD}, {"ref": "f10", "key": "fireflies.counter.x", "url": REVIEW},
          {"ref": "f12", "key": "fireflies.counter.y", "url": "https://fireflies.ai/blog"}]
    assert uncitable(["f3", "f10", "f12"], ev, "fireflies") == ["f10 (javisreview.com)"] and uncitable(["f3", "f12"], ev, "fireflies") == []

@pytest.mark.parametrize("tool, url, citable", [
    ("autogen", "https://microsoft.github.io/autogen/stable/x", True), ("autogen", "https://randomblogger.github.io/x", False),     # github.io is a platform
    ("inspect-ai", "https://inspect.aisi.org.uk/x", True), ("inspect-ai", "https://somecharity.org.uk/x", False),                   # org.uk is a suffix
    ("smolagents", "https://huggingface.co/docs/smolagents/x", True), ("smolagents", "https://huggingface.co/someone/x", False),    # one host, many owners
    ("google-meet", "https://sites.google.com/view/someone", False), ("google-meet", "https://support.google.com/meet/thread/1", False),
    ("linkedin-learning", "https://www.linkedin.com/posts/someone", False),
    ("zoom", "https://www.zoom.com/en/products/x", True), ("zoom", "https://community.zoom.com/t/1", False),                         # user content on a maker's own domain
    ("microsoft-teams", "https://answers.microsoft.com/x", False), ("microsoft-teams", "https://learn.microsoft.com/en-us/answers/questions/1", False)])
def test_the_vendor_is_its_own_homepage_site_never_the_platform_it_is_hosted_on(tool, url, citable):
    """AS-232: a tool's own site comes from its homepage in the tracked data; a shared host, a public suffix or a forum is not the vendor."""
    from airstack.publication import uncitable
    assert uncitable(["f1"], [{"ref": "f1", "key": f"{tool}.counter.a", "url": url}], tool) == ([] if citable else [f"f1 ({url.split('/')[2].removeprefix('www.')})"])

def test_a_held_outcome_reaches_the_page_without_the_commentary_host_it_names():
    """A reassessment held for citing a review keeps the host in the stored outcome (the record); the public projection names no host."""
    out = hold({"why": "held: the judge cited f10 (javisreview.com)", "sync_report": {"still_lapsed": [[4, "held: f10 (javisreview.com)"]]}})
    assert not held_text(json.dumps(out)) and out["why"] == "held: the judge cited f10 (a third-party review)"

@pytest.mark.private_data
@pytest.mark.skipif((paths.DATA / "PUBLISHED.md").exists(), reason="this checks the private record, which the published snapshot is not")
def test_the_stored_verdict_that_rests_on_a_review_is_exactly_what_the_gate_now_holds():
    """AS-232: the demo's verdict 4 (kept as the record, not re-issued here) cites the review; today's gate would have held it, and only for that."""
    import sqlite3
    from airstack.publication import uncitable
    citations, evidence = [json.loads(x) for x in sqlite3.connect(f"file:{paths.DEMO_DB}?mode=ro", uri=True)
                           .execute("SELECT json_extract(judge_output, '$.citations'), evidence FROM verdicts WHERE id=4").fetchone()]
    assert uncitable(citations, evidence, "fireflies") == ["f10 (javisreview.com)"]
