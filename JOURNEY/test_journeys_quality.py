# spec: AS-066 AS-100 AS-102 AS-104 AS-112 AS-120 AS-121 AS-223 AS-260 AS-280 AS-335 AS-343
import json, pytest, re
from .journey_kit import SMALL_TEXT, _open, chip, pick, plan, until, view


def test_j08_phone_width_stacks_tables_and_keeps_tap_targets(browser, base_url):
    ctx, pg, errors = _open(browser, base_url, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce")
    assert pg.evaluate("document.documentElement.scrollWidth") <= 391
    assert pg.evaluate(SMALL_TEXT) == []
    assert pg.query_selector("#cmpGo").bounding_box()["height"] >= 44          # the Compare link, before a tool is chosen
    assert pg.query_selector(".tape a").bounding_box()["height"] >= 24          # the moving tape is still a usable target
    pick(pg, "Fathom"); pg.wait_for_selector("#setup"); assert pg.query_selector("#setup").bounding_box()["height"] >= 44; chip(pg, '#uses .chip[data-v="In person"]')
    for sel in (".nav a", "#q", "#platforms .chip", "#plans .chip", "#devices .chip", ".foot a", "#mcpLink"):
        assert pg.query_selector(sel).bounding_box()["height"] >= 44, sel
    view(pg, "how")
    for sel in (".step", ".tab", "#replay"):
        assert pg.query_selector(sel).bounding_box()["height"] >= 44, sel
    assert pg.evaluate("getComputedStyle(document.querySelector('#lt thead')).display") == "none"   # rows stack with their labels
    pg.click("#tab-exec"); assert pg.evaluate("document.documentElement.scrollWidth") <= 391
    view(pg, "markets"); pg.wait_for_selector("#mvt tbody tr"); pg.click('#mvt th button[data-s="stars"]')        # sorting still works on a phone
    assert pg.get_attribute('#mvt th button[data-s="stars"]', "aria-pressed") == "true" and pg.evaluate("document.documentElement.scrollWidth") <= 391
    assert pg.evaluate("document.documentElement.scrollWidth") <= 391 and not errors
    ctx.close()

def test_j09_keyboard(page):
    page.focus("#q")
    page.keyboard.type("fat"); page.wait_for_selector("#ta:not([hidden])")
    page.keyboard.press("Escape"); page.wait_for_selector("#ta", state="hidden")
    page.keyboard.type("h"); page.keyboard.press("Enter"); page.wait_for_selector("#answer .aw")
    page.focus("#setup"); page.keyboard.press("Enter"); assert page.get_attribute("#setup", "aria-expanded") == "true"      # Your setup · Change opens from the keyboard
    page.focus('#plans .chip[aria-checked="true"]'); page.keyboard.press("ArrowRight")
    assert page.get_attribute('#plans .chip[data-v="Business Plus"]', "aria-checked") == "true" and page.inner_text("#answer .aw") in ("Retire", "Notes covered")
    page.click("#mcpLink"); page.wait_for_timeout(300)
    assert page.evaluate("Math.abs(document.getElementById('agents').getBoundingClientRect().top) < 120")   # the footer's MCP link goes to the connect section

def test_j28_no_screen_ever_shows_a_stringified_object_or_undefined(page):
    until(page, "window.AIRSTACK_MARKET && document.querySelector('#vendors tbody tr')")
    bad = lambda: [w for w in ("[object", "undefined", "NaN", "null") if w in page.inner_text("body")]
    assert bad() == [], bad()
    for name in ("Fathom", "Pinecone", "Claude Code"):
        if page.locator("#change").is_visible(): page.click("#change")
        pick(page, name); page.wait_for_timeout(50)
        assert bad() == [], (name, bad())
        for chip in page.query_selector_all("#uses .chip, #platforms .chip")[:4]:
            if chip.is_visible(): chip.click(); assert bad() == [], (name, chip.inner_text(), bad())
    view(page, "markets"); page.click("#mvMore"); until(page, "document.querySelectorAll('#mvt tbody tr').length > 100")
    assert bad() == [], bad()
    for v in ("insights", "makers", "agents", "how"):                                       # every view, not only the first one
        view(page, v); page.wait_for_timeout(300); assert bad() == [], (v, bad())

def test_j31_when_the_market_data_cannot_load_the_page_says_so(browser, base_url):
    ctx, pg, errors = _open(browser, base_url, service_workers="block")      # no worker, so the block below is what the page sees
    ctx.route("**/market-data.js", lambda r: r.abort())
    pg.reload(); pg.wait_for_selector("#trend .lb button", state="attached")
    pick(pg, "Fathom"); until(pg, "document.querySelector('#answer').innerText.includes('could not be loaded')")
    assert "Loading the checks" not in pg.inner_text("#answer") and pg.is_hidden("#market")          # never an endless spinner
    pg.click("#change"); pick(pg, "Pinecone")
    assert pg.is_visible("#toolcard") and "Pinecone" in pg.inner_text("#pickedName")                  # tools without a replacement model still open
    assert not errors; ctx.close()
    ctx = browser.new_context(service_workers="block", reduced_motion="reduce")
    ctx.route("**/insights.json", lambda r: r.abort())
    pg = ctx.new_page(); errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(base_url.split("#")[0] + "#/insights"); pg.wait_for_selector("#insBody [role=status]")
    assert pg.locator("#insights").is_visible() and "could not be loaded" in pg.inner_text("#insSub")
    assert "No measurements are shown" in pg.inner_text("#insBody") and not errors
    ctx.close()

def test_j32_motion_plays_when_allowed_ends_at_rest_and_switches_off_when_asked(browser, base_url):
    for pref, plays in (("no-preference", True), ("reduce", False)):
        ctx, pg, errors = _open(browser, base_url, reduced_motion=pref)
        pick(pg, "Pinecone"); pg.wait_for_selector("#toolcard .tiles")
        assert (pg.evaluate("getComputedStyle(document.querySelector('.lb .bar i')).animationName") == "grow") is plays, pref
        until(pg, "[...document.querySelectorAll('.lb .bar i, .lb li, .tile')].filter(e => e.offsetParent).every(e => getComputedStyle(e).opacity === '1' && ['none', 'matrix(1, 0, 0, 1, 0, 0)'].includes(getComputedStyle(e).transform))", timeout=4000)   # what is on screen is at rest: nothing left half-drawn
        assert not errors; ctx.close()

UNTRUSTED_MARKUP = '"><img src=x onerror=window.__pwn=1><svg onload=window.__pwn=2><script>window.__pwn=4</script>'

INJECT_FIXTURE = """;(function(P){const bad=s=>typeof s==='string'&&(/^https?:/.test(s)?'javascript:window.__pwn=3':(/[A-Z ]/.test(s)?s+P:s));
const walk=o=>{for(const k in o){const v=o[k];if(typeof v==='string')o[k]=bad(v);else if(v&&typeof v==='object')walk(v)}};
if(window.AIRSTACK_DATA)walk(window.AIRSTACK_DATA);if(window.AIRSTACK_MARKET)walk(window.AIRSTACK_MARKET)})(%r);""" % UNTRUSTED_MARKUP

def test_j34_nothing_on_screen_shows_a_spend_figure_a_stale_api_name_or_a_wrong_noun(browser, base_url):
    """Public copy uses the current vocabulary and contains no internal usage figures."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    pick(pg, "Fireflies"); pg.wait_for_selector("#answer .aw")
    pg.evaluate("document.querySelector('#tab-exec').click()")
    text = pg.evaluate("document.getElementById('main').textContent")   # the rendered page, not the script that renders it
    assert not re.search(r"\d[\d,.]*\s+credits|\$\s?\d|Which phone|\bseat:", text, re.I), re.findall(r".{30}(?:\d[\d,.]*\s+credits|\$\s?\d|Which phone|\bseat:).{30}", text, re.I)[:4]
    assert "A local agent gets the same recorded answer" in text and "Local MCP · assess" in text
    assert "hosted function or model" in text and not pg.locator("#runMcp").count()
    view(pg, "agents")
    assert "airstack.mcp_server" in pg.inner_text("#agCli") and "seat" not in pg.inner_text("#agents")
    assert not errors; ctx.close()

def test_j35_no_verdict_reason_repeats_a_third_party_review_or_a_banned_word(browser, base_url):
    """AS-223: the publication hold keeps commentary and allegations out of every public reason, citation and source list."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    pick(pg, "Fireflies"); pg.wait_for_selector("#answer .aw")
    pg.evaluate("document.querySelector('#tab-exec').click()")
    text = pg.evaluate("document.getElementById('main').textContent")
    text = re.sub(r"\(Our AirStack seat id is [AB]\.\)", "", text)       # the recorded A/B prompt is shown verbatim: it is the record of what the model was asked, so it is not rewritten
    assert not re.search(r"\bseat\b|lawsuit|alleg|Voiceprint|\bReview 20\d\d|javisreview", text, re.I); ctx.close()

def test_j37_on_a_phone_the_verdict_changes_in_view_and_movers_rows_are_compact(browser, base_url):
    """At 375 px, chip changes remain in view and Movers rows stay compact."""
    ctx = browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True, device_scale_factor=2, reduced_motion="reduce", service_workers="block"); pg = ctx.new_page()
    errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(base_url); pg.wait_for_selector("#trend .lb button", state="attached"); view(pg, "markets"); pg.wait_for_selector("#mvt tbody tr")
    top12 = pg.evaluate("(() => { const rows = [...document.querySelectorAll('#mvt tbody tr:not(.prow)')].slice(0, 12); return rows[11].getBoundingClientRect().bottom - rows[0].getBoundingClientRect().top })()")
    assert top12 <= 1100, f"top 12 Movers rows are {top12:.0f}px tall"
    row = pg.locator("#mvt tbody tr:not(.prow) .rowtog").first
    assert row.get_attribute("aria-expanded") == "false"; row.tap(); assert row.get_attribute("aria-expanded") == "true"
    assert pg.locator("#mvt tbody tr.open td[data-l='GitHub stars']").first.is_visible()
    pick(pg, "Fathom"); pg.wait_for_selector("#answer .aw")
    pg.locator("#setup").tap()                                                                   # the choices sit behind Your setup · Change
    pg.locator("#platforms .chip[data-v='Zoom']").tap(); pg.wait_for_timeout(100)
    seen = []
    for plan in ("Zoom Workplace Basic", "Zoom Workplace paid plan"):
        pg.locator(f"#plans .chip[data-v='{plan}']").tap(); pg.wait_for_timeout(150)
        box = pg.locator("#strip").bounding_box()
        assert box and box["y"] >= 0 and box["y"] + box["height"] <= 812, ("the strip must be inside the viewport", box)
        assert box["height"] <= 57, ("the strip is one line, at most 56 px", box)
        seen.append(pg.inner_text("#strip"))
    assert seen[0] != seen[1] and all(seen), seen
    assert not errors; ctx.close()

def test_j38_suggestions_typed_right_after_a_blur_are_not_closed_by_its_late_timer(browser, base_url):
    """A delayed blur cannot close suggestions that were reopened after it."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    pg.fill("#q", "pine"); pg.wait_for_selector("#ta li[role=option]")
    pg.evaluate("document.getElementById('q').blur(); document.getElementById('q').focus()")      # blur starts the timer, focus shows again straight away
    pg.fill("#q", "pinec"); pg.wait_for_timeout(400)
    assert pg.locator("#ta li[role=option]").count() >= 1 and not pg.evaluate("document.getElementById('ta').hidden"), "the late blur timer closed the suggestions"
    assert not errors; ctx.close()

def test_j33_external_text_is_rendered_as_inert_content(browser, base_url):
    """External text stays text, and generated links use HTTP or HTTPS."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 860}, service_workers="block"); pg = ctx.new_page()
    csp, errors = [], []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: csp.append(m.text) if "Content Security Policy" in m.text else None)
    def poison_js(route):
        r = route.fetch(); route.fulfill(response=r, body=r.text() + INJECT_FIXTURE)
    def poison_json(route):
        import json
        def walk(o):
            if isinstance(o, dict): return {k: walk(v) for k, v in o.items()}
            if isinstance(o, list): return [walk(v) for v in o]
            if isinstance(o, str): return "javascript:window.__pwn=3" if o.startswith("http") else (o + UNTRUSTED_MARKUP if re.search(r"[A-Z ]", o) else o)
            return o
        r = route.fetch(); route.fulfill(response=r, body=json.dumps(walk(r.json())))
    ctx.route(re.compile(r"/(site|market)-data\.js"), poison_js); ctx.route(re.compile(r"/chain-data\.json"), poison_json)
    pg.goto(base_url); pg.wait_for_selector("#trend .lb button", state="attached")
    pick(pg, "Pinecone"); pg.wait_for_selector("#toolcard .tiles")
    pg.locator("#toolcard [data-chain]").first.click(); pg.wait_for_selector("#chainTbl tbody tr", timeout=90_000)    # chain-data.json is 14.8 MB and this test rewrites every string in it
    pg.keyboard.press("Escape"); tiles = pg.locator("#toolcard .tiles").count()
    pg.click("#change"); view(pg, "how"); pg.locator("#market").scroll_into_view_if_needed(); pg.wait_for_timeout(500)   # the market table, in How it works
    assert pg.evaluate("window.__pwn") is None, "external text executed as script"
    assert pg.evaluate("[...document.querySelectorAll('a[href]')].filter(a => /^(javascript|data|vbscript):/i.test(a.getAttribute('href').trim())).length") == 0
    assert pg.evaluate("document.querySelectorAll('img[src=x], svg[onload], [onerror]').length") == 0, "external markup became elements"
    assert tiles == 1, "the page did not render the injected fixture"
    assert not csp, csp; ctx.close()

def test_j30_in_page_links_never_undo_a_choice(page):
    view(page, "markets"); page.wait_for_selector("#mvt tbody tr"); page.click("#mvMore"); until(page, "document.querySelectorAll('#mvt tbody tr').length > 100")
    page.click('#mvt a[data-app="Fathom"]')                                              # a Movers row opens the tool in Check yours
    page.wait_for_selector("#answer .aw")
    assert page.inner_text("#pickedName") == "Fathom" and page.evaluate("location.hash") == "#app=fathom"
    page.evaluate("location.hash = '#market'"); page.wait_for_timeout(100)               # following any other in-page link keeps the choice
    assert page.inner_text("#pickedName") == "Fathom"
    view(page, "overview")
    page.click("#profile [data-chain]"); page.keyboard.press("Escape")
    assert page.evaluate("location.hash") == "#app=fathom"                               # closing the evidence chain restores the address of the tool

CPU_LOOP = "(() => { const t = performance.now(); let s = 0; for (let i = 0; i < 5e6; i++) s += Math.sqrt(i); return performance.now() - t })()"

CPU_REF_MS = 8.0                                                                    # that loop takes about 6 ms on a developer laptop

def cpu_factor(browser):
    """How much slower than a developer laptop this machine runs JavaScript: 1 on one, up to 4 on a shared runner. The performance gates
    emulate a phone as a multiple of the machine's own speed (Lighthouse's own advice is to calibrate its slowdown to the host), so a slow
    runner is not graded as a slower phone: Lighthouse's slowdown is divided by this, the interaction budgets below are multiplied by it."""
    pg = browser.new_page(); pg.goto("about:blank")
    ms = min(pg.evaluate(CPU_LOOP) for _ in range(5)); pg.close()
    return min(4.0, max(1.0, ms / CPU_REF_MS))

def test_j27_every_input_responds_within_a_frame_or_two(browser, base_url):
    """Speed is a feature with a budget: main-thread time per interaction, measured at 4x slower CPU. Typical cost is 1-5 ms; the budget is generous so CI noise cannot flake it."""
    speed = cpu_factor(browser)
    ctx, pg, errors = _open(browser, base_url)
    until(pg, "window.AIRSTACK_MARKET && document.querySelector('#vendors tbody tr')")
    pg.click("#q"); until(pg, "!!__airstack.byName('Ganglia')")                  # focusing loads the directory: typeahead is timed over all 21,000 records, as a person meets it
    cdp = ctx.new_cdp_session(pg); cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    steps = [("misspelled typeahead", "(i => { const q = document.querySelector('#q'); q.value = ['figmma','notoin','cursro','supaase'][i%4]; q.dispatchEvent(new Event('input')) })", 40, 100),
             ("typeahead", "(i => { const q = document.querySelector('#q'); q.value = ['c','cu','cursor','figm','salesf'][i%5]; q.dispatchEvent(new Event('input')) })", 40, 50),
             ("pick a tool", "(i => __airstack.selectTool(__airstack.byId(['pinecone','qdrant','aider'][i%3])))", 30, 50),
             ("open an assessed tool", "(i => __airstack.selectTool(__airstack.byName('Fathom')))", 40, 50),          # 40 samples: with 20, "p95" was the single slowest run
             ("platform chip", "(i => document.querySelectorAll('#platforms .chip')[i%3].click())", 40, 50),
             ("sort Movers", "(i => document.querySelectorAll('#mvt th button')[i%3].click())", 40, 50),
             ("show all 130 Movers", "(i => document.querySelector('#mvMore').click())", 10, 100)]
    for name, fn, n, budget in steps:
        p95 = pg.evaluate("""([fn, n]) => { const ts = []; for (let i = 0; i < n; i++) { const t0 = performance.now(); eval(fn)(i); document.querySelector('#check').offsetHeight; ts.push(performance.now() - t0) }
            ts.sort((a, b) => a - b); return ts[Math.floor(n * .95)] }""", [fn, n])
        assert p95 < budget * speed, f"{name}: p95 {p95:.1f} ms is over {budget} ms x {speed:.2f} (this machine's speed against a laptop)"
    assert not errors; ctx.close()

def test_j11_works_offline_after_the_first_visit(browser, base_url):
    ctx, pg, errors = _open(browser, base_url)
    pg.evaluate("navigator.serviceWorker.ready.then(() => true)")
    until(pg, "navigator.serviceWorker.controller !== null", timeout=10000)
    ctx.set_offline(True)
    pg.reload(); pg.wait_for_selector("#trend .lb button", timeout=10000)
    pick(pg, "Fathom"); pg.wait_for_selector("#answer .aw", timeout=10000)
    assert pg.inner_text("h1") == "See the software market move." and pg.inner_text("#answer .aw") in ("Retire", "Notes covered") and not errors
    ctx.close()

def test_j12_release_quality_contract(browser, base_url):
    """Measure loading, stability, semantics and accessible names in Chrome."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 860}, reduced_motion="reduce", service_workers="block")
    ctx.add_init_script("""
      window.__quality = {lcp: 0, cls: 0, blocking: 0};
      new PerformanceObserver(xs => { for (const x of xs.getEntries()) __quality.lcp = Math.max(__quality.lcp, x.startTime) })
        .observe({type: 'largest-contentful-paint', buffered: true});
      new PerformanceObserver(xs => { for (const x of xs.getEntries()) if (!x.hadRecentInput) __quality.cls += x.value })
        .observe({type: 'layout-shift', buffered: true});
      new PerformanceObserver(xs => { for (const x of xs.getEntries()) __quality.blocking += Math.max(0, x.duration - 50) })
        .observe({type: 'longtask', buffered: true});
    """)
    pg = ctx.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(base_url); pg.wait_for_selector("#trend .lb button", state="attached"); pg.wait_for_timeout(1000)
    metrics = pg.evaluate("""() => ({
      fcp: performance.getEntriesByName('first-contentful-paint')[0]?.startTime || 0,
      lcp: __quality.lcp, cls: __quality.cls, blocking: __quality.blocking
    })""")
    assert 0 < metrics["fcp"] <= 1500 and 0 < metrics["lcp"] <= 2500, metrics
    assert metrics["cls"] <= 0.02 and metrics["blocking"] <= 300, metrics

    nodes = ctx.new_cdp_session(pg).send("Accessibility.getFullAXTree")["nodes"]
    value = lambda node, key: (node.get(key) or {}).get("value", "")
    roles = {value(node, "role") for node in nodes if not node.get("ignored")}
    assert {"main", "navigation", "heading", "combobox"} <= roles, sorted(roles)
    unnamed = [(value(node, "role"), node.get("nodeId")) for node in nodes if not node.get("ignored")
               and value(node, "role") in {"button", "link", "searchbox", "textbox", "combobox"} and not value(node, "name").strip()]
    assert unnamed == []
    semantics = pg.evaluate("""() => ({
      h1: document.querySelectorAll('h1').length,
      title: document.title,
      description: document.querySelector('meta[name=description]')?.content || '',
      canonical: document.querySelector('link[rel=canonical]')?.href || '',
      search: ['role', 'aria-controls', 'aria-autocomplete'].map(a => document.querySelector('#q').getAttribute(a)),
      schema: [...document.querySelectorAll('script[type="application/ld+json"]')].every(s => { try { JSON.parse(s.textContent); return true } catch { return false } }),
      small: (%s)()
    })""" % SMALL_TEXT)
    assert semantics["h1"] == 1 and semantics["title"].startswith("AirStack") and len(semantics["description"]) >= 80
    assert semantics["canonical"] == "https://airstack.bot/" and semantics["search"] == ["combobox", "ta", "list"]
    assert semantics["schema"] and semantics["small"] == [] and not errors
    ctx.close()

def test_j54_the_app_views_each_have_a_tab_route_and_working_back_and_forward(browser, base_url):
    """AS-260: one view at a time; every tab lands on a visible view and marks itself current; back and forward move between views;
    a product link (#app=) opens in Overview from any view; old section anchors land on the view that holds them."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    tabs = [a.get_attribute("data-view") for a in pg.query_selector_all(".nav a[data-view]")]
    assert tabs == ["overview", "compare", "markets", "insights", "calendar", "makers", "agents", "how"]
    holds = {"overview": "#check", "compare": "#cmpSec", "markets": "#movers", "insights": "#insights", "calendar": "#calendar", "makers": "#leaders", "agents": "#agents", "how": "#life"}
    for v in tabs:
        pg.click(f'.nav a[data-view="{v}"]'); pg.wait_for_selector(f'.nav a[data-view="{v}"][aria-current="page"]')
        assert pg.locator(holds[v]).is_visible(), v
        assert all(not pg.locator(o).is_visible() for w, o in holds.items() if w != v), v                  # one view at a time
        assert pg.locator('.nav a[aria-current="page"]').count() == 1
    pg.go_back(); pg.wait_for_selector('.nav a[data-view="agents"][aria-current="page"]')
    pg.go_back(); pg.wait_for_selector('.nav a[data-view="makers"][aria-current="page"]')
    pg.go_forward(); pg.wait_for_selector('.nav a[data-view="agents"][aria-current="page"]')
    pg.evaluate("location.hash = '#app=fathom'"); pg.wait_for_selector("#answer .aw")                 # a product link opens in Overview
    assert pg.locator('.nav a[data-view="overview"][aria-current="page"]').count() == 1 and pg.inner_text("#pickedName") == "Fathom"
    pg.evaluate("location.hash = '#movers'"); pg.wait_for_selector('.nav a[data-view="markets"][aria-current="page"]')   # an old anchor
    assert pg.title().startswith("Markets · AirStack")
    assert not errors; ctx.close()
    ctx, pg, errors = _open(browser, base_url.split("#")[0] + "#/agents", viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce")
    until(pg, "document.querySelector('.nav a[aria-current=page]').dataset.view === 'agents'")
    until(pg, "(() => { const a=document.querySelector('.nav a[aria-current=page]').getBoundingClientRect(), n=document.querySelector('.nav').getBoundingClientRect(); return a.left >= n.left && a.right <= n.right })()")
    pg.evaluate("location.hash = '#/how'")
    until(pg, "document.querySelector('.nav a[aria-current=page]').dataset.view === 'how'")
    until(pg, "(() => { const a=document.querySelector('.nav a[aria-current=page]').getBoundingClientRect(), n=document.querySelector('.nav').getBoundingClientRect(); return a.left >= n.left && a.right <= n.right })()")
    assert not errors; ctx.close()
