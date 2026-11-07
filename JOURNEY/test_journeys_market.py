# spec: AS-102 AS-104 AS-254 AS-255 AS-257 AS-265 AS-285 AS-298 AS-317 AS-326 AS-327 AS-328
import re
from .journey_kit import _open, until, view


def test_j14_movers_show_real_signals_each_linked_to_its_source(page):
    view(page, "markets"); page.wait_for_selector("#mvt tbody tr")
    assert page.locator("#mvt tbody tr").count() == 12                       # top 12 by default
    page.click("#mvMore"); until(page, "document.querySelectorAll('#mvt tbody tr').length > 100")   # the rest of the rows arrive a frame after the first 24
    total = page.locator("#mvt tbody tr").count()
    assert total == len(page.evaluate("() => window.AIRSTACK_MARKET.movers.rows")) >= 30
    for a in page.query_selector_all("#mvt tbody a.src"):                    # every number links to the registry, search or repo it came from
        assert a.get_attribute("href").startswith("https://") and a.get_attribute("target") == "_blank"
    labels = [c.inner_text() for c in page.query_selector_all("#lanes .chip")]
    assert labels[0] == "All" and "Vector databases" in labels and not any("[object" in l or "undefined" in l for l in labels)   # real names, never a stringified object
    page.click('#lanes .chip[data-v="Vector databases"]')
    assert all("Vector databases" in r.inner_text() for r in page.query_selector_all("#mvt tbody tr"))
    page.click('#mvt th button[data-s="stars"]')
    assert page.get_attribute('#mvt th button[data-s="stars"]', "aria-pressed") == "true"
    t = page.inner_text("#movers")
    assert "attention, not users" in t and ("Catalog only" in t or "Check yours" in t)

def test_j15_the_market_every_cell_is_sourced_or_says_not_observed(page):
    """The card and matrix use one vocabulary."""
    view(page, "how"); page.wait_for_selector("#vendors tbody tr")
    rows = page.query_selector_all("#vendors tbody tr")
    assert len(rows) == 5
    for r in rows:
        for td in r.query_selector_all("td")[1:]:
            assert td.query_selector("a.src") or "Not observed" in td.inner_text(), td.inner_text()
    assert "quotes found on their pages" in page.inner_text("#fleet") and "Muse Spark" in page.inner_text("#fleet")
    m = page.inner_text("#market")
    assert not re.search(r"[$€£]\s?\d", m) and "Not known yet" in m and "Notes covered" in m and "Keep" in m
    assert "Retire ·" not in m and "on Android, iPhone and a computer" in m

def test_j39_trending_lists_only_tools_above_their_own_recent_level_and_above_the_volume_floor(browser, base_url):
    """A rebound from a trough and a small absolute move do not become a trend."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    shown = pg.inner_text("#trend")
    assert "OpenHands" not in shown and "Skyvern" not in shown and "Laminar" not in shown, shown[:300]
    assert "above their own 4-week level" in shown and "5,000" in shown                 # the list says what it is
    until(pg, "window.AIRSTACK_MARKET && window.AIRSTACK_MARKET.movers", 15000)            # the full data loads after first paint
    bad = pg.evaluate("""() => { const M = window.AIRSTACK_MARKET.movers.rows; return M.filter(r => r.dl.delta != null && r.dl.value >= 5000 && !(r.dl.vsBase != null && r.dl.vsBase < 0)).length }""")
    assert bad >= 8 and not errors; ctx.close()

def test_j40_the_first_screen_never_shows_a_rebound_as_the_top_mover_even_before_the_full_data_loads(browser, base_url):
    """First-paint mover rows use the same baseline as the full dataset."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 860}, service_workers="block"); pg = ctx.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.route(re.compile(r"/market-data\.js"), lambda route: route.abort())           # the full data never arrives: only the first-paint rows exist
    pg.goto(base_url); pg.wait_for_selector("#trend .lb button", state="attached"); pg.wait_for_selector("#mvt tbody tr", state="attached")   # the section itself is hidden when the full data fails; its first-paint rows still must not mislead
    assert "OpenHands" not in pg.inner_text("#trend") and "Skyvern" not in pg.inner_text("#trend")
    first = pg.evaluate("document.querySelector('#mvt tbody tr:not(.prow) td[data-l=\\'Tool\\'] b').textContent")
    assert first not in ("OpenHands", "Laminar", "Browser Use", "Skyvern"), first
    ctx.close()

def test_j52_the_stats_card_renders_the_sites_counts_and_its_dated_tape(browser, base_url):
    """AS-254: /stats.svg, opened as an image would be, shows the counts and a dated momentum tape."""
    root = base_url.rsplit("/", 1)[0] + "/" if base_url.endswith(".html") else base_url
    ctx = browser.new_context(reduced_motion="reduce"); pg = ctx.new_page(); pg.goto(root + "stats.svg")
    text = pg.text_content("svg")
    assert "software products" in text and "read from their own pages" in text and "4-week level" in text and "updated" in text
    assert pg.locator(".tk").count() >= 2
    ctx.close()

def test_j53_the_market_map_draws_only_measured_tools_and_says_what_its_areas_and_colours_mean(browser, base_url):
    """AS-257: a tile per tool with downloads, area by downloads within its lane, colour by change against its own 4-week level;
    no baseline means hatched, never coloured; lanes without download counts are named, not drawn empty; a tile opens its tool."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    view(pg, "markets"); until(pg, "!!(window.AIRSTACK_MARKET && window.AIRSTACK_MARKET.movers)"); pg.wait_for_selector("#mmap .tile")
    rows = pg.evaluate("window.AIRSTACK_MARKET.movers.rows.filter(r => r.dl && r.dl.value > 0).map(r => [r.name, r.dl.vsBase])")
    tiles = pg.locator("#mmap .tile")
    assert tiles.count() == len(rows)
    by = dict(rows)
    for i in range(tiles.count()):
        t = tiles.nth(i); name, label, cls = t.get_attribute("data-app"), t.get_attribute("title"), t.get_attribute("class")
        assert "downloads in 7 days" in label
        assert (" none" in cls) == (by[name] is None) and ("%" not in t.inner_text() or by[name] is not None)
    note = pg.inner_text("#mmapNote")
    assert "Areas compare within a lane, not across" in note and "Not drawn:" in note
    big = pg.locator("#mmap button.tile").first; first = big.get_attribute("data-app"); big.click()
    pg.wait_for_function("n => document.querySelector('#pickedName') && document.querySelector('#pickedName').textContent === n", arg=first)
    assert not errors; ctx.close()

def test_j56_insights_place_only_measured_products_and_say_what_each_axis_is(browser, base_url):
    """The role map, category KPIs and ecosystem graph agree with insights.json."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    view(pg, "insights"); pg.wait_for_selector("#aimap"); pg.wait_for_selector(".t.kpi tbody tr"); pg.wait_for_selector(".hubs li")
    I = pg.evaluate("fetch('insights.json').then(r => r.json())")
    mine = lambda cat: [q for q in I["map"]["points"] if q[0].startswith("Q") == cat]            # the two populations: cataloged categories, and everything Wikidata lists
    label = pg.get_attribute("#aimap", "aria-label")
    assert f"{len(mine(False)):,} products" in label and f"{I['map']['unplaced']:,} more miss an input" in label      # the categories first: the question people ask
    bands = lambda: [int(x.inner_text().split("\n")[-1].replace(",", "")) for x in pg.query_selector_all(".aiy span")]
    assert bands() == [sum(1 for q in mine(False) if q[4] == b) for b in (2, 1, 0)]
    pg.click('.aipop .chip[data-pop="all_listed"]'); pg.wait_for_timeout(150)
    assert bands() == [sum(1 for q in mine(True) if q[4] == b) for b in (2, 1, 0)] and "predates AI" in pg.inner_text("#insights").replace("long ", "")   # the other population, and why it reads differently
    s = pg.inner_text("#insights")
    assert "not market share" in s and "what its own pages say" in s
    assert pg.evaluate("document.querySelector('#aimap').width") > 0                         # drawn at its real size once the view opened
    rows = pg.locator(".t.kpi tbody tr:not(.dept)")
    assert rows.count() == sum(1 for c in I["categories"].values() if c["researched"])
    assert [h.inner_text().lower() for h in pg.query_selector_all(".t.kpi tbody tr.dept th")] == [d.lower() for d in dict.fromkeys(c["department"] for c in sorted(I["categories"].values(), key=lambda c: I["departments"].index(c["department"])) if c["researched"])]
    first = next(c for c in I["categories"].values() if c["researched"] and c["department"] == "Sales")
    assert f"{first['free_plan']} of {first['researched']}" in pg.inner_text(".t.kpi")             # a share always carries its count and its denominator
    assert [h.inner_text().lower() for h in pg.query_selector_all(".t.kpi thead th")][2:-1] == [k["label"].lower() for k in I["kpis"]]
    assert not errors; ctx.close()

def test_j81_insights_reads_as_a_sourced_argument_not_a_widget_grid(browser, base_url):
    """AS-255: the first read is a thesis and three measured findings; exact populations and values remain in the visual and table."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    view(pg, "insights"); pg.wait_for_selector("#insBody .ins-lede")
    assert "vendor positioning" in pg.inner_text(".ins-lede").lower() and "not product quality, adoption or market share" in pg.inner_text(".ins-lede")
    findings = pg.query_selector_all(".ins-findings > li")
    assert len(findings) == 3 and all(re.search(r"\d", f.inner_text()) for f in findings)
    questions = [h.inner_text() for h in pg.query_selector_all(".ins-chapter > h3")]
    assert questions == ["Where does AI appear in vendors’ own words?", "What do categories consistently disclose?", "Which products form the connective tissue?"]
    assert "Read the split, not a score" in pg.inner_text(".ins-annotation")
    assert pg.locator(".t.kpi").count() == 1 and pg.locator(".hubs li").count() >= 5 and not errors
    ctx.close()

def test_j57_what_changed_lists_each_vendors_own_announcements_by_day_with_blogs_behind_a_toggle(browser, base_url):
    """Each product appears once under its latest update, with earlier items grouped beneath it;
    blog posts only when asked for; titles are the publishers' own and every row links to its source."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    pg.evaluate("document.querySelector('#news').scrollIntoView()"); pg.wait_for_selector("#newsList .nrow")
    N = pg.evaluate("fetch('news.json').then(r => r.json())")
    rows = pg.query_selector_all("#newsList .nrow")
    titles = {i["title"] for i in N["items"]}
    for r in rows[:20]:
        a = r.query_selector(".nt a.ext"); assert a.inner_text() in titles and a.get_attribute("href").startswith("http")
        assert r.query_selector(".nk").inner_text().lower() in ("changelog", "release", "hn")             # no blog until asked for
    days = [h.inner_text() for h in pg.query_selector_all("#newsList .nday > h3")]
    assert days and len(days) == len(set(days))                                                          # one heading per day
    names = [b.inner_text() for b in pg.query_selector_all("#newsList .nrow > .who b")]
    assert len(names) == len(set(names)), names                                                           # each product once, at its latest update
    assert "from each vendor’s own feed" in pg.inner_text("#newsSub").lower() and "publishers’ own" in pg.inner_text("#newsSub")
    pg.click('#newsKinds .chip[data-kind="blog"]'); pg.wait_for_timeout(100)
    assert any(r.inner_text().lower().endswith("blog") or "blog" in r.query_selector(".nk").inner_text().lower() for r in pg.query_selector_all("#newsList .nrow"))
    assert not errors; ctx.close()

def test_j64_the_calendar_draws_only_recorded_or_published_dates_with_their_sources(browser, base_url):
    """AS-298: the calendar contains records, published dates and AirStack review dates—never a cadence forecast or source-less mark."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    view(pg, "calendar"); pg.wait_for_selector("#calGrid i")
    E = pg.evaluate("fetch('events.json').then(r => r.json())"); today = E["source"]["built_for"]
    assert pg.locator("#calGrid i").count() == 79 * 7
    assert pg.locator("#calGrid i.t").count() == 1 and pg.get_attribute("#calGrid i.t", "data-d") == today
    ahead = pg.query_selector_all("#calAhead .crow")
    assert ahead and all(r.query_selector(".cs").inner_text().split(" · ")[0] in ("Published support date", "AirStack review date") for r in ahead)
    assert all(e["status"] in ("observed", "scheduled", "recheck") and e["precision"] == "day" and e["url"].startswith("https://") for e in E["events"])
    assert not any("expected" in e["title"].lower() or e.get("until") for e in E["events"])
    names = [b.inner_text() for b in pg.query_selector_all("#calAhead .crow > .who b")]
    assert len(names) == len(set(names)), names                                                          # one next date per product; later dates fold under it
    busy = pg.query_selector("#calGrid i.o4, #calGrid i.o3, #calGrid i.o2"); busy.click(); pg.wait_for_selector("#calDay:not([hidden]) .crow")
    d = busy.get_attribute("data-d"); assert d[:4] in pg.inner_text("#calDay h3") and str(int(d[8:])) in pg.inner_text("#calDay h3")   # the drawer names the day picked
    assert all(any(s in r.inner_text() for s in ("Observed record", "Published support date", "AirStack review date")) for r in pg.query_selector_all("#calDay .crow"))
    assert pg.get_attribute('#calKinds .chip[data-kind="hacker news"]', "aria-pressed") == "false"
    pg.click('#calKinds .chip[data-kind="support"]'); pg.wait_for_timeout(100)
    assert not any("end of" in r.inner_text() for r in pg.query_selector_all("#calAhead .crow"))
    assert not errors; ctx.close()

def test_j82_missing_market_signals_are_named_not_drawn_as_holes(browser, base_url):
    """AS-326: missing source, prior week, baseline, release and AirStack coverage are named states; a measured zero stays numeric."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    view(pg, "markets"); pg.wait_for_selector("#mvt tbody tr"); pg.click("#mvMore")
    until(pg, "document.querySelectorAll('#mvt tbody tr').length > 100")
    text = pg.inner_text("#movers")
    assert "insufficient 4-week baseline" in text.lower() and "Catalog only" in text
    assert not re.search(r"(^|\s)—($|\s)", text)
    notes = [n.inner_text() for n in pg.query_selector_all("#mvt .state-note")]
    assert notes and all(n in {"No registry record", "No prior week", "No weekly baseline", "No HN record", "No GitHub record", "No release recorded", "Catalog only"} for n in notes)
    zeros = [td.inner_text().split()[0] for td in pg.query_selector_all('#mvt td[data-l="HN stories, 7 days"]')]
    assert "0" in zeros and not errors
    ctx.close()

def test_j68_the_makers_view_is_searchable_filterable_and_every_state_is_a_link(browser, base_url):
    """AS-317: o/makers.json (the same ranking as the /o/ pages) in an explorable view: search, country, kind and sort; the address holds the state,
    so a second browser opening it sees exactly the same list; every maker links to its own page."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    view(pg, "makers"); pg.wait_for_selector("#mkList tr td")
    M = pg.evaluate("fetch('o/makers.json').then(r => r.json())")
    assert f"{len(M['rows']):,} of {len(M['rows']):,} makers" in pg.inner_text("#mkCount")
    assert pg.inner_text("#mkList tr:first-child th") == next(r[1] for r in M["rows"] if r[7]) or pg.locator("#mkList tr:first-child th a").count() == 1   # the largest ranked business leads
    germany = [r for r in M["rows"] if r[2] == "Germany"]
    pg.select_option("#mkCountry", "Germany"); pg.select_option("#mkSort", "products"); pg.fill("#mkQ", "a"); pg.wait_for_timeout(150)
    want = sorted((r for r in germany if "a" in r[1].lower()), key=lambda r: (-r[6], r[1]))
    assert pg.inner_text("#mkCount").startswith(f"{len(want):,} of") and pg.inner_text("#mkList tr:first-child th") == want[0][1]
    assert pg.locator("#mkList tr:first-child th a").get_attribute("href") == f"/o/{want[0][0]}/"
    assert "country=Germany" in pg.url and "sort=products" in pg.url and "q=a" in pg.url
    other = ctx.new_page(); other.goto(pg.url); other.wait_for_selector("#mkList tr td")
    assert other.input_value("#mkCountry") == "Germany" and other.input_value("#mkSort") == "products" and other.input_value("#mkQ") == "a"   # a shared link restores the view
    assert other.inner_text("#mkList tr:first-child th") == want[0][1]
    pg.click("#mkReset"); pg.wait_for_timeout(100); assert "country=" not in pg.url
    assert not errors; ctx.close()

def test_j69_markets_covers_every_kind_of_software_sized_by_documentation_and_says_what_it_is_not(browser, base_url):
    """AS-285, AS-257: a picker of the taxonomy's categories draws that category's products as tiles sized by how widely each is documented (a count every
    product has), says it is not market share, draws no change, and states how many listed products carry no category yet."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    view(pg, "markets"); pg.wait_for_selector("#tyMap .tile")
    M = pg.evaluate("fetch('t/map.json').then(r => r.json())")
    assert pg.locator("#tyPick option").count() == len(M["nodes"])                                   # every category with products, nothing else
    pg.select_option("#tyPick", "design"); pg.wait_for_timeout(200)
    top = M["nodes"]["design"][4]; tiles = pg.locator("#tyMap a.tile")
    assert pg.locator("#tyMap .tile").count() == len(top) and tiles.first.get_attribute("href") == f"#app={top[0][0]}"      # the most documented first, each one a link
    assert f"{top[0][2]} Wikipedia and sister-site pages" in tiles.first.get_attribute("aria-label")
    note = pg.inner_text("#tyNote"); assert "not market share" in note and f"{M['total'] - M['placed']:,} of {M['total']:,} listed products carry no category yet" in note
    assert pg.get_attribute("#tyPage", "href") == "/t/design/" and pg.locator("#tyMap .tile.up1, #tyMap .tile.dn1").count() == 0          # no change is invented
    assert not errors; ctx.close()
