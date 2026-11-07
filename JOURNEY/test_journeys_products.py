# spec: AS-103 AS-104 AS-106 AS-131 AS-137 AS-140 AS-233 AS-237 AS-239 AS-248 AS-250 AS-251 AS-258 AS-259 AS-264 AS-270 AS-295 AS-306 AS-347 AS-348 AS-D01
import pytest, re
from urllib.parse import urlsplit
from .journey_kit import DATA, _open, pick, until, view


def test_j70_a_misspelled_name_still_finds_the_tool(page):
    """AS-347: names are searched with a typo (two letters swapped, one dropped, one doubled) and the right tool still comes first. A fixed sample of the
    page's own tools, so the set is the same on every run; a few misses are allowed (two tools a typo apart are rightly ambiguous)."""
    names = sorted({n for n in page.evaluate("window.AIRSTACK_DATA.index.map(r => r[1])") if len(re.sub(r"[^a-z0-9]", "", n.lower())) >= 6})[::7]
    assert len(names) >= 40
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    misses = []; total = 0
    for name in names:
        k = re.sub(r"[^A-Za-z0-9]", "", name); i = len(k) // 2
        for typo in (k[:i] + k[i + 1] + k[i] + k[i + 2:], k[:i] + k[i + 1:], k[:i] + k[i] + k[i:]):
            total += 1
            first = page.evaluate("""t => { const q = document.querySelector('#q'); q.value = t; q.dispatchEvent(new Event('input'));
                const f = document.querySelector('#ta li[role=option] .who span:last-child'); return f ? f.textContent : '' }""", typo)
            if norm(first) != norm(name):
                misses.append((name, typo, first))
    assert len(misses) <= total * 0.05, (len(misses), total, misses[:8])
    page.evaluate("q => { const i = document.querySelector('#q'); i.value = q; i.dispatchEvent(new Event('input')) }", "supaase")
    assert "Supabase" in page.inner_text("#ta li[role=option]")

def test_j04_search_finds_any_tracked_tool_by_name_or_category_and_opens_it(page):
    page.focus("#q")
    page.keyboard.type("pinec"); page.wait_for_selector("#ta li[role=option]")       # "pine" alone is the exact name of a listed email client, which rightly comes first
    assert page.inner_text("#ta li[role=option]").startswith("Pinecone")
    page.keyboard.press("Enter")
    assert page.is_hidden("#ta") and page.inner_text("#pickedName") == "Pinecone" and "Vector databases" in page.inner_text("#pickedLane")
    assert "Pinecone" in page.inner_text("#toolcard") and page.is_hidden("#answer")          # a tool without a replacement model still opens a real page
    page.click("#change"); page.fill("#q", "vector")                                           # typing a category lists its tools
    page.wait_for_selector("#ta li[role=option]")
    assert all("Vector databases" in li.inner_text() for li in page.query_selector_all("#ta li[role=option]"))
    page.keyboard.press("Escape"); assert page.is_hidden("#ta")

def test_j06_sources_are_dated_linked_and_fingerprinted(page):
    page.evaluate("document.getElementById('detail').scrollIntoView()")
    until(page, "[...document.querySelectorAll('#p-sources .hv')].every(e => e.classList.contains('ok'))", timeout=5000)
    rows = page.query_selector_all("#p-sources tbody tr")
    assert len(rows) == len(page.evaluate(DATA)["sources"]) >= 6
    links = page.query_selector_all("#p-sources a")
    assert all(a.get_attribute("href").startswith("https://") and a.get_attribute("target") == "_blank" for a in links)
    hosts = [urlsplit(link.get_attribute("href")).hostname for link in links]
    assert "9to5google.com" in hosts and any("17020724" in a.get_attribute("href") for a in links)
    assert "(replaced)" in page.inner_text("#p-sources") and "20e5f611" in page.inner_text("#p-sources")   # the hash the backend test pins

def test_j07_history_and_execution_show_the_real_work(page):
    view(page, "how"); page.click("#tab-history")
    h = page.inner_text("#p-history")
    assert page.is_hidden("#p-sources") and "Needs a second look" in h and h.count("Keep") >= 3
    page.click("#tab-exec")
    x = page.inner_text("#p-exec")
    d = page.evaluate(DATA)
    assert page.locator("#p-exec .t tbody tr").count() >= len(d["execution"]["rows"])
    if d["meta"]["live"]:
        assert "resp_" in x and "muse-spark-1.3" in x and "0.92" in x and "fake-" not in x
        assert page.locator(".ab").count() == len(d["execution"]["ab"]) and all(page.locator(".ab ol").nth(i).locator("li").count() == 3 for i in range(2 * len(d["execution"]["ab"])))
        assert "Asked AirStack get_verdict" in page.inner_text(".ab")
    assert "Meet’s in-person notes aren’t included in Business Starter." in x or "Meet's in-person notes aren't included in Business Starter." in x   # the reason the endpoint serves, in plain words
    page.click("#tab-sources"); page.keyboard.press("ArrowRight")
    assert page.get_attribute("#tab-history", "aria-selected") == "true"  # tabs are keyboard-operable

def test_j24_a_tool_profile_opens_with_only_verified_facts_and_a_deep_link(browser, base_url):
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    until(pg, "window.AIRSTACK_MARKET && document.querySelector('#mvt .pbtn')")
    view(pg, "markets"); pg.click("#mvt .pbtn >> nth=0")
    pg.wait_for_selector(".prow dl.kv"); row = pg.query_selector(".prow"); t = row.inner_text()         # the facts load with the first profile opened
    assert "WHAT IT SAYS IT DOES" in t.upper() and "NOT OBSERVED" in t.upper() and "facts extracted with Muse Spark" in t
    assert all(a.get_attribute("href").startswith("https://") for a in row.query_selector_all("a.src"))        # every fact links its page
    h = pg.evaluate("location.hash"); assert h.startswith("#tool=")
    pg.click("#mvt .pbtn >> nth=0"); assert pg.locator(".prow").count() == 0 and pg.evaluate("location.hash") == "#/markets"      # toggles closed; the address is the view again
    pg.evaluate("h => { location.hash = h }", h); pg.wait_for_selector(".prow")                                  # the same link pasted into this tab reopens it
    pg.go_back(); until(pg, "document.querySelectorAll('.prow').length === 0")                          # back closes it
    pg.go_forward(); pg.wait_for_selector(".prow")                                                                 # forward restores it
    other = pg.evaluate("""() => Object.keys(window.AIRSTACK_MARKET.profiles).find(k => !document.querySelector(`#mvt .pbtn[data-p="${k}"]`))""")
    assert other, "a profile outside the visible rows is needed to prove deep links reach beyond them"
    name = pg.evaluate("id => window.AIRSTACK_MARKET.movers.rows.find(r => r.id === id).name", other)
    ctx2, pg2, errors2 = _open(browser, base_url + "#tool=" + other, reduced_motion="reduce")                      # a fresh load straight onto a tool
    pg2.wait_for_selector(".prow dl.kv", timeout=8000)                                                              # its facts load with it
    assert name in pg2.inner_text(".prow")
    assert not errors and not errors2
    ctx.close(); ctx2.close()

def test_j25_the_evidence_chain_shows_every_link_and_admits_what_is_missing(browser, base_url):
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    view(pg, "how"); pg.wait_for_selector("#vendors tbody tr")
    opener = pg.locator("#vendors [data-chain] >> nth=0"); opener.click()
    pg.wait_for_selector("#chainTbl tbody tr")
    summary = pg.inner_text("#chainSum")
    assert "verified on their pages by code" in summary and "re-checked live" in summary and "independent sources: none yet" in summary
    first = pg.locator("#chainTbl tbody tr >> nth=0")
    row = first.inner_text()
    assert first.locator("td").count() == 7
    assert first.locator("td[data-l=Source] a.ext").count() == 1
    assert "HTTP 200" in row and "quote found on the page" in row and "“" in row
    assert all(a.get_attribute("href").startswith("https://") for a in pg.query_selector_all("#chainTbl a.ext"))
    assert "vendor’s own site" in pg.inner_text("#chainNote") and "None is an independent party" in pg.inner_text("#chainNote")   # the gap is stated, not hidden
    assert "Not re-checked yet" in pg.inner_text("#chainTbl") or "unchanged" in pg.inner_text("#chainTbl") or "still on it" in pg.inner_text("#chainTbl")
    h = pg.evaluate("location.hash"); assert h.startswith("#chain=")
    pg.keyboard.press("Escape"); assert pg.is_hidden("#chainSec") and pg.evaluate("location.hash") == "#/how"     # back to the view's own address
    assert pg.evaluate("document.activeElement.dataset.chain") is not None                                        # focus returns to the button that opened it
    ctx2, pg2, errors2 = _open(browser, base_url + h, reduced_motion="reduce")                                    # a pasted link lands on the chain
    pg2.wait_for_selector("#chainTbl tbody tr", timeout=8000)
    assert pg2.inner_text("#chainT").startswith("Evidence chain ·")
    D = pg2.evaluate("fetch('chain-data.json').then(r => r.json())")
    classes = {f["class"] for e in D["entities"].values() for f in e["facts"]}
    assert "vendor" in classes and classes <= set(D["classes"])                                                    # every class is a declared one
    assert all(f["class"] == "independent" for e in D["entities"].values() for f in e["facts"] if f["host"] == "9to5google.com")
    cur = [f for f in D["entities"]["cursor"]["facts"] if f["host"] == "cursor.com"]
    assert cur and all(f["class"] == "vendor" for f in cur)                                                        # a vendor's own domain is the vendor's
    assert not errors and not errors2
    ctx.close(); ctx2.close()

def test_j29_the_search_box_counts_the_tools_it_searches(page):
    d = page.evaluate("window.AIRSTACK_DATA")
    n = len(d["index"]) + d["dir"]["products"] + d["dir"]["orgs"]
    assert n >= 10000 and page.get_attribute("#q", "placeholder") == f"Search {n:,} products"   # computed from the data, never typed

def test_j36_a_tool_without_a_replacement_check_states_its_coverage_first(browser, base_url):
    """The first thing under the picked name is available coverage."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    pick(pg, "Pinecone"); pg.wait_for_selector("#toolcard .tiles"); pg.wait_for_selector("#toolcard details.nobsd")   # the facts load with the page
    first = pg.evaluate("document.querySelector('#toolcard').firstElementChild.className + '|' + document.querySelector('#toolcard').firstElementChild.innerText")
    assert first.startswith("cover|") and "Market signals · current snapshot" in first and "Own-page facts ·" in first, first
    assert pg.locator("#toolcard details.nobsd").count() == 1 and not pg.evaluate("document.querySelector('#toolcard details.nobsd').open")
    assert re.search(r"\d+ fields? not on the pages read", pg.inner_text("#toolcard summary.nobs"))
    assert "isn’t built yet" not in pg.inner_text("#toolcard") and "Renewal verdict" not in pg.inner_text("#toolcard")
    t = pg.inner_text("#toolcard")
    assert "found on its page by code" in t and "not independent confirmation" in t and "verified" not in t.lower(), t[-400:]
    assert not errors; ctx.close()

def test_j26_no_tracked_tool_is_a_dead_end(page):
    """Persona sweep: a person who uses a tool in ANY category finds it by typing and lands on something useful, never an apology."""
    tools = page.evaluate("window.AIRSTACK_DATA.index")
    assert len(tools) >= 100 and len({t[2] for t in tools}) >= 10
    one_per_lane = {}
    for t in tools: one_per_lane.setdefault(t[2], t)
    until(page, "window.AIRSTACK_MARKET")
    for tid, name, lane, *_ in one_per_lane.values():                                   # a cataloged entry also carries its aliases
        if page.locator("#change").is_visible(): page.click("#change")
        page.fill("#q", name[:5]); page.wait_for_selector("#ta li[role=option]")
        shown = [li.inner_text().split("\n")[0] for li in page.query_selector_all("#ta li[role=option]")]
        if name not in shown:                                                            # a shared prefix ("Googl" matches 30 products): the full name must then come first
            page.fill("#q", name); page.wait_for_selector("#ta li[role=option]")
            assert page.query_selector_all("#ta li[role=option]")[0].inner_text().split("\n")[0] == name, (name, "not first when typed in full")
        page.fill("#q", name); page.press("#q", "Enter"); page.wait_for_selector("#picked:not([hidden])")
        assert page.inner_text("#pickedName") == name
        card = page.inner_text("#toolcard")
        useful = (
            page.locator("#answer .aw").is_visible()
            or page.locator("#toolcard .cover .on").count() > 0
            or (page.locator("#toolcard dl.kv dt").count() >= 3 and page.locator("#toolcard a.ext").count() > 0)
        )
        assert useful, (name, "opened an empty page")
        assert "isn’t checked yet" not in page.inner_text("#check") and "don’t track" not in page.inner_text("#check")   # no apology for a tool we track
    page.click("#change"); assert page.is_visible("#trend .lb button")

def test_j41_a_tools_page_shows_that_tool_and_the_worked_example_stays_with_meeting_notes(browser, base_url):
    """AS-239: OpenRouter's page used to carry the Google Meet market table, the replayed Fireflies example and its record."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    view(pg, "how"); assert pg.locator("#life").is_visible() and "worked example" in pg.inner_text("#lifeSub")   # How it works keeps it, labelled
    pick(pg, "OpenRouter"); pg.wait_for_selector("#toolcard .tiles"); view(pg, "how")
    for sec in ("#market", "#life", "#detail"):
        assert not pg.locator(sec).is_visible(), sec
    view(pg, "overview")
    text = pg.inner_text("#top") + pg.inner_text("#check")
    assert not re.search(r"Google Meet|Business Standard|Fireflies|replayed", text), re.findall(r".{30}(?:Google Meet|Business Standard|Fireflies|replayed).{30}", text)[:3]
    pick(pg, "Fireflies"); pg.wait_for_selector("#answer .aw"); view(pg, "how")
    assert pg.locator("#market").is_visible() and pg.locator("#life").is_visible()                          # a meeting-notes tool still gets its market and the example
    assert not errors; ctx.close()

def test_j44_everyday_business_software_is_found_by_name_alias_or_category_and_its_page_says_only_what_is_known(browser, base_url):
    """AS-237: "gmail" used to say we don't track it. The catalog covers the paid products companies renew; each says what is known and no more."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    for typed in ("gmail", "gmial", "google mail"):                                   # the name, a typo, an alias
        pg.fill("#q", typed); pg.wait_for_selector("#ta li[role=option]")
        first = pg.query_selector_all("#ta li[role=option]")[0].inner_text()
        assert first.startswith("Gmail") and "Email and calendar" in first, (typed, first)
    pg.press("#q", "Enter"); pg.wait_for_selector("#toolcard .kv")
    card = pg.inner_text("#toolcard")
    assert "Market position · not observed" not in card and "Renewal verdict" not in card and "reached" in card and "AirStack’s classification" in card
    assert pg.get_attribute("#toolcard dl a.ext", "href").startswith("https://")
    if pg.evaluate("!!(window.AIRSTACK_MARKET.profiles || {}).gmail"):             # researched: its own-page facts, each a quote found on its page
        assert re.search(r"Own-page facts · \d+ quotes found", card) and "What its own pages say" in card
    else:                                                                            # not yet: says so, and claims nothing else
        assert pg.locator("#toolcard .cover").count() == 0 and "nothing else is claimed" in card
    pg.click("#change"); pg.fill("#q", "Slack"); pg.wait_for_selector("#ta li[data-i]"); pg.press("#q", "Enter"); pg.wait_for_selector("#toolcard .kv")   # the category list left the first screen (the /c/ pages list every category); a cataloged tool is found by search
    assert pg.inner_text("#pickedName") == "Slack" and not pg.locator("#market").is_visible()
    assert not errors; ctx.close()

def test_j47_every_software_product_and_company_wikidata_records_is_searchable_and_says_it_is_listed_not_researched(browser, base_url):
    """AS-248: the directory loads on first search; a listed product shows Wikidata's record, linked, and claims nothing else; its maker opens
    the company's card with what it makes; the taxonomy browses from "software" down, every count from the data."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    pg.click("#q"); until(pg, "window.__dir_probe = document.querySelector('#q') && true")
    D = pg.evaluate("fetch('directory.json').then(r => r.json())")
    top = next(p for p in D["products"] if p[5] and p[2] and D["orgs"][p[5][0]][5] != "person")   # the best-known listing with a description and a company as maker
    pg.fill("#q", top[1]); pg.wait_for_selector("#ta li[data-i]")
    pg.keyboard.press("Enter"); pg.wait_for_selector("#toolcard dl.kv")
    card = pg.inner_text("#toolcard")
    assert pg.inner_text("#pickedName") == top[1] and f"Wikidata {top[0]}" in card and "CC0" in card and "Wikidata’s description" in card
    researched = pg.locator("#toolcard .cover .on").count() > 0
    assert researched or ("hasn’t read" in card and "nothing else is claimed" in card)
    names = [re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")[:60] or "x" for n in [*(p[1] for p in D["products"]), *(o[0] for o in D["orgs"].values() if o[5] != "person")]]
    readable = re.sub(r"[^a-z0-9]+", "-", top[1].lower()).strip("-")[:60] or "x"
    assert pg.evaluate("location.hash") == f"#app={readable if names.count(readable) == 1 else top[0]}"          # a readable name where it is unique, the id where two read the same
    assert pg.locator(f"#toolcard a[href='https://www.wikidata.org/wiki/{top[0]}']").count() == 1
    maker = top[5][0]
    pg.click(f"#toolcard button[data-pick='{maker}']"); pg.wait_for_selector("#toolcard h3")
    assert pg.inner_text("#pickedName") == D["orgs"][maker][0] and "What it makes" in pg.inner_text("#toolcard") and top[1] in pg.inner_text("#toolcard")
    pg.goto(base_url + "#app=" + top[0]); pg.reload(); pg.wait_for_selector("#toolcard dl.kv")          # a pasted directory link opens once the directory loads
    assert pg.inner_text("#pickedName") == top[1]
    pg.click("#toolcard .crumb button[data-type]"); pg.wait_for_selector("#trend .tl button")                 # the type crumb on a card opens the taxonomy; the first screen no longer has a button for it
    crumb = pg.inner_text("#trend .crumb").lower()                                            # labels are uppercased by CSS
    assert crumb.startswith("software") and f"{len(D['products']):,} products" in crumb
    first = pg.locator("#trend .tl button").first; label = first.inner_text().rsplit(" ", 1)[0]; first.click()
    assert label.lower() in pg.inner_text("#trend .crumb").lower() and pg.locator("#trend ol.lb li").count() > 0
    assert not errors; ctx.close()

def test_j48_a_profile_shows_what_its_quotes_mean_not_the_page_furniture_they_came_from(browser, base_url):
    """Profile facts exclude download controls, navigation text and model vendors."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    pick(pg, "Cursor"); pg.wait_for_selector("#toolcard h3 ~ dl.kv")
    t = pg.inner_text("#toolcard")
    assert "SDK LANGUAGES" not in t.upper() and "Download for" not in t
    models = next((l for l in t.splitlines() if "Composer" in l), "")
    assert models and not any(v in models.split(", ") for v in ("Anthropic", "OpenAI", "Cursor", "Grok models"))
    assert not errors; ctx.close()

def test_j49_list_prices_are_shown_as_written_each_linked_to_its_page_with_its_quote(browser, base_url):
    """AS-250: the one kind of dollar figure on screen is a list price as written on the product's own pricing page, linked, with its quote."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    Q = pg.evaluate("fetch('pricing.json').then(r => r.json())")
    pid = next(k for k in ("notion", "linear", "asana", "slack") if k in Q)
    name = pg.evaluate("id => window.AIRSTACK_DATA.index.find(r => r[0] === id)[1]", pid)
    pick(pg, name); pg.wait_for_selector("#toolcard table.prices")
    links = pg.query_selector_all("#toolcard table.prices a.ext")
    assert len(links) == len(Q[pid]["plans"]) and all(l.get_attribute("href") == Q[pid]["url"] for l in links)
    for l, p in zip(links, Q[pid]["plans"]):
        assert p["price"] in l.inner_text() and p["quote"] in (l.get_attribute("title") or "")
    pg.wait_for_selector("#toolcard table.alt")
    assert "starting at" in pg.inner_text("#toolcard table.alt thead").lower()               # headers are uppercased by CSS
    assert not errors; ctx.close()

def test_j50_a_product_shows_open_source_alternatives_from_github_each_linked_with_its_repository_attention_and_licence(browser, base_url):
    """AS-251: the open-source projects for the same job, from GitHub's search API, labelled as a lead."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    pick(pg, "Higgsfield"); pg.wait_for_selector("#toolcard ol.oss.mt16 li")
    items = pg.query_selector_all("#toolcard ol.oss.mt16 li")                      # the candidates offered; those below the bar sit apart, collapsed
    assert "repository attention—not use, sentiment or trust" in pg.inner_text("#toolcard")
    assert 1 <= len(items) <= 8 and all(i.query_selector("a").get_attribute("href").startswith("https://github.com/") for i in items)
    assert "★" in items[0].inner_text() and "forks" in items[0].inner_text() and "open issues and pull requests" in items[0].inner_text() and "discussions" in items[0].inner_text()
    assert "Automated checks, not an audit" in pg.inner_text("#toolcard")
    assert not errors; ctx.close()

def test_j80_a_product_separates_known_channels_measured_attention_and_omits_unmeasured_sources(browser, base_url):
    """AS-264, AS-295: a public channel is not presented as conversation, and unavailable sources do not become empty UI."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    C = pg.evaluate("fetch('community.json').then(r => r.json())")
    pid = next(i[0] for i in pg.evaluate(DATA)["index"] if i[0] in C["catalog"])
    name = next(i[1] for i in pg.evaluate(DATA)["index"] if i[0] == pid)
    pick(pg, name); pg.wait_for_selector("#toolcard .community")
    text = pg.inner_text("#toolcard .community")
    low = text.lower()
    assert "attention, kept separate from adoption" in low and "not a live scrape" in low
    assert "not proof that people are discussing or using" in low and "discussion appears only when a dated source record exists" in low
    assert "not indexed" not in low and "unavailable" not in low
    assert pg.locator("#toolcard .community-links a[href^='https://']").count() >= 1
    assert not errors; ctx.close()

def test_j55_a_product_says_why_teams_use_its_category_and_which_open_models_do_the_job(browser, base_url):
    """AS-258, AS-259: the category guide is labelled as AirStack's, not the vendor's; open models carry Hugging Face's own counts and their licence."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    pick(pg, "Higgsfield"); pg.wait_for_selector("#toolcard .guide")
    g = pg.inner_text("#toolcard .guide")
    assert "Why teams use" in g and "not a claim by Higgsfield" in g and "who uses it" in g.lower() and "Watch for" in g
    pg.wait_for_selector("#toolcard .hfm li")
    models = pg.query_selector_all("#toolcard .hfm li a")
    assert models and all(a.get_attribute("href").startswith("https://huggingface.co/") for a in models)
    t = pg.inner_text("#toolcard")
    assert "Hugging Face’s own 30-day count" in t and "check each licence" in t
    assert not errors; ctx.close()

def test_j58_a_directory_product_shows_its_list_prices_when_its_pricing_page_was_read(browser, base_url):
    """Directory products use the same sourced list-price contract as catalog products."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    Q = pg.evaluate("fetch('pricing.json').then(r => r.json())")
    qid = next((k for k in Q if re.fullmatch(r"Q\d+", k) and Q[k]["plans"]), None)
    if not qid:
        ctx.close(); pytest.skip("pricing.json has no directory product yet")
    pg.evaluate(f"location.hash = '#app={qid}'"); pg.wait_for_selector("#toolcard table.prices", timeout=20000)
    assert all(a.get_attribute("href") == Q[qid]["url"] for a in pg.query_selector_all("#toolcard table.prices a.ext"))
    assert not errors; ctx.close()

def test_j62_every_product_and_organization_carries_a_monogram_drawn_from_its_initials(browser, base_url):
    """AS-270: a suggestion and the open product carry a monogram: initials on a hue fixed by the product's website; no third-party mark is fetched."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    sent = []; pg.on("request", lambda r: sent.append(r.url) if not r.url.startswith(re.match(r"https?://[^/]+", base_url).group(0)) else None)
    pg.fill("#q", "Notion"); pg.wait_for_selector("#ta li[data-i] .av[data-i]")
    av = pg.query_selector("#ta li[data-i] .av[data-i]")
    assert re.fullmatch(r"[A-Z0-9]{1,2}", av.get_attribute("data-i")) and av.get_attribute("aria-hidden") == "true"
    pg.press("#q", "Enter"); pg.wait_for_selector("#pickedMono .av[data-i]")
    assert pg.get_attribute("#pickedMono .av", "data-i") == "N" and sent == []                          # nothing fetched from anyone else
    assert not errors; ctx.close()
