# spec: AS-066 AS-100 AS-101 AS-102 AS-104 AS-105 AS-106 AS-131 AS-134 AS-239 AS-242 AS-252 AS-253 AS-256 AS-283 AS-328 AS-331 AS-343 AS-346 AS-366 AS-D03
import re
from urllib.parse import urlsplit
from .journey_kit import DATA, SMALL_TEXT, _open, chip, pick, plan, until, view


TYPE_SIZES = """() => [...new Set([...document.querySelectorAll('body *')].filter(e => e.offsetParent !== null
    && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())).map(e => getComputedStyle(e).fontSize))]"""

def checker(pg, name="Fathom", meeting="Online", device=None):
    """Open an assessed tool, optionally in person on a device."""
    pick(pg, name); pg.wait_for_selector("#answer .aw")
    if meeting == "In person":
        chip(pg, '#uses .chip[data-v="In person"]'); chip(pg, f'#devices .chip[data-v="{device or "Android"}"]')

def test_j01_first_look_is_the_claim_and_one_action(page):
    assert "AirStack" in page.title()
    assert page.inner_text("h1") == "See the software market move." and page.locator("h1").count() == 1
    assert "compare every category" in page.inner_text(".sub") and "linked to its source" in page.inner_text(".sub")
    assert page.evaluate("document.querySelector('#q').getBoundingClientRect().top") < 900          # the one action, search, is on the first screen
    honest = page.inner_text("#honest")
    live = page.evaluate(DATA)["meta"]["live"]
    d = page.evaluate(DATA)
    assert not page.query_selector("#kpis") and not page.query_selector("#cats") and not page.query_selector("#alltypes")   # one way in: the search box (and Compare beside it), not tiles, a dropdown and a taxonomy button
    assert f"Scope: {d['dir']['researched']:,} researched products · every fact quoted from its own page" in honest     # AS-239: one proof line, its number counted from the data
    assert "Compare" in page.inner_text("#cmpGo") and page.get_attribute("#cmpGo", "href") == "#compare="   # the second way in
    assert ("researched with Muse Spark" in honest) if live else ("verified from stored evidence" in honest)   # one provenance line for the whole site
    body = page.inner_text("body")
    assert not re.search(r"\$\s?\d", body) and not re.search(r"\b" + "ki" + "ll" + r"\b", body, re.I)
    assert not re.search(r"fake-|fixture|\bseat\b|LIVE|sample", body), "scenario words or internals on the page"
    faces = page.inner_text("#top") + page.inner_text("#check")
    assert not re.search(r"\b(meet|fireflies)\.[a-z_]+|sha256", faces, re.I), "machine keys on the answer"
    assert page.evaluate(SMALL_TEXT) == []                                # nothing under 12px
    assert len(page.evaluate(TYPE_SIZES)) <= 5                            # five type sizes, no more
    foot = page.inner_text(".foot")
    assert "AirStack" in foot and "Muse Spark" in foot and "GitHub" in foot and "MCP" in foot

def test_j02_check_yours_answers_every_plan_without_a_request(page):
    page.wait_for_selector("#vendors tbody tr", state="attached")        # the market has loaded; from here on nothing may be requested
    assert page.is_hidden("#answer") and page.is_hidden("#bench")        # nothing is preselected for the user
    sent = []; page.on("request", lambda r: sent.append(r.url) if not r.url.split("?")[0].endswith("/directory.json") else None)   # the search box loads the directory (a static file); answers load nothing
    checker(page, "Fireflies")
    assert page.inner_text("#setup").upper().startswith("ASSUMING\nGOOGLE BUSINESS STANDARD, ONLINE") and page.is_visible("#picked")   # the assumptions are stated, and are the mainstream ones
    assert page.get_attribute('#uses .chip[aria-checked="true"]', "data-v") == "Online" and page.get_attribute("#qDevW", "hidden") is not None and page.is_hidden("#qs")   # the choices are one line until you change them
    assert page.inner_text("#answer .aw") == "Notes covered" and "may be able to stop paying" in page.inner_text("#answer .aline")      # the bundle covering the notes is not a cancellation (review P0)
    chip(page, '#needs .chip[data-n="none"]')
    assert page.inner_text("#answer .aw") == "Retire" and "ASSUMING" not in page.inner_text("#setup").upper()   # choosing something ends the assumption
    chip(page, '#uses .chip[data-v="In person"]')
    assert page.inner_text("#answer .aw") == "One more question" and "Which device" in page.inner_text("#answer .aline")   # a device is asked, never assumed
    assert "Not observed" not in page.inner_text("#answer") and page.locator("#answer dl").count() == 0                  # a pending question is not an unobserved fact
    assert not page.inner_text("#setup .sv").strip().endswith(",")                                                       # no dangling separator where the device would be
    assert page.locator('#devices .chip[aria-checked="true"]').count() == 0
    chip(page, '#devices .chip[data-v="Android"]')
    a = page.inner_text("#answer")
    assert page.inner_text("#answer .aw") == "Retire" and "You can stop paying for this, for what you told us" in a and "Business Standard includes it" in a
    if page.evaluate(DATA)["meta"]["live"]:
        assert "Judged by muse-spark-1.3" in a and "tokens" in a and "confidence" not in a      # the receipt: real calls; self-reported confidence lives in Execution only
    links = page.query_selector_all("#answer a.ext")
    assert links and all(l.get_attribute("href").startswith("https://") and l.get_attribute("target") == "_blank" for l in links)
    plan(page, "Business Starter")
    a = page.inner_text("#answer")
    assert page.inner_text("#answer .aw") == "Keep" and "Meet's in-person notes aren't included in Business Starter." in a
    assert page.locator("#answer .how").get_attribute("open") is None and "With Business Starter" not in page.inner_text("#answer")   # the diagram is behind How we decided, closed
    page.click("#answer .how summary"); assert page.locator("#answer .mk.unmet").count() == 1 and "With Business Starter" in page.inner_text("#answer .needs")
    page.wait_for_function("document.querySelectorAll('#answer .cmap path').length > 0")                               # the lines are drawn on the frame after the answer renders
    assert page.locator("#answer .needs li").count() >= 2 and page.locator("#answer .needs li.unmet").count() == 1 and page.locator("#answer .cmap path").count() == page.locator("#answer .needs li").count()   # the coverage map: one line per need, to whatever covers it
    plan(page, "Business Plus"); chip(page, '#devices .chip[data-v="iPhone"]')
    assert page.inner_text("#answer .aw") in ("Retire", "Notes covered") and "Rules only · no model call" in page.inner_text("#answer")   # never claims a model it didn't call
    assert sent == [], sent                                              # every answer is a lookup: no request, no model call

def test_j02b_reduced_motion_shows_every_step_without_animation(page):
    page.evaluate("document.getElementById('life').scrollIntoView()")
    assert page.get_attribute("#st3", "aria-selected") == "true"         # the current state, immediately
    assert page.inner_text("#replay") == "Replay"

def test_j03_as_it_happened_old_advice_never_looks_current(page):
    view(page, "how"); page.click("#st1")
    rows = page.query_selector_all("#lt tbody tr")
    assert len(rows) == 2 and all("Needs a second look" in r.inner_text() for r in rows)
    assert page.locator("#lt .lw.lapsed").count() == 2                   # the old answer is struck, not presented as current
    cap = page.inner_text("#cap")
    assert "13 Aug 2026" in cap and "10:50 AM PT" in cap and page.get_attribute("#cap a", "href").startswith("https://workspaceupdates.googleblog.com/2026/08/")
    page.click("#st2")
    r0, r1 = [r.inner_text() for r in page.query_selector_all("#lt tbody tr")]
    if page.evaluate(DATA)["meta"]["live"]:
        assert "Needs a second look" in r0 and "confident" in r0         # the gate withheld a low-confidence answer
        assert "Current" in r1 and "Keep" in r1 and "Business Starter" in r1
    page.click("#st3")
    r0 = page.query_selector_all("#lt tbody tr")[0].inner_text()
    assert "Retire" in r0 and "Current" in r0
    page.keyboard.press("ArrowLeft"); assert page.get_attribute("#st2", "aria-selected") == "true"   # steps are keyboard-selectable

def test_j03b_the_replay_steps_through_recorded_events_once(browser, base_url):
    ctx, pg, errors = _open(browser, base_url)
    view(pg, "how"); pg.wait_for_selector("#vendors tbody tr")           # the worked example lives in How it works; then scroll, as a reader would
    pg.evaluate("document.getElementById('lifepanel').scrollIntoView({block:'center'})")
    until(pg, "document.getElementById('replay').textContent === 'Stop'", timeout=4000)
    until(pg, "document.getElementById('st3').getAttribute('aria-selected') === 'true' && document.getElementById('replay').textContent === 'Replay'", timeout=10000)
    assert not errors
    ctx.close()

def test_j05_an_untracked_tool_is_saved_on_this_device_only(page):
    checker(page, "Fathom")
    page.fill("#q", "Qzzv Ledger"); page.keyboard.press("Enter")                           # a name nothing tracks (Salesforce and the like are cataloged now)
    page.wait_for_selector("#nf:not([hidden])")
    assert "don’t track" in page.inner_text("#nfText") and page.is_hidden("#answer") and page.is_hidden("#bench")      # no leftover answer for another tool
    page.click("#save")
    assert page.inner_text("#save") == "Saved on this device" and page.is_disabled("#save")          # never claims it was sent anywhere
    assert "requested" not in page.inner_text("#check").lower()

def test_j16_check_yours_covers_zoom_and_teams_from_verified_quotes(page):
    checker(page, "Otter"); plan(page, "Zoom Workplace paid plan")
    a = page.inner_text("#answer")
    hosts = [(urlsplit(link.get_attribute("href")).hostname or "").removeprefix("www.") for link in page.query_selector_all("#answer a[href]")]
    assert page.inner_text("#answer .aw") == "Notes covered" and "zoom.com" in hosts and "quote found on the page" in a
    assert not re.search(r"[$€£]\s?\d", a) and page.is_hidden("#qDevW")          # no prices; a device matters only for Google in person
    assert "otter lists" in page.inner_text("#profile").lower()
    plan(page, "Teams without Premium")
    assert page.inner_text("#answer .aw") == "Keep" and "Teams Premium or Microsoft Copilot" in page.inner_text("#answer")
    plan(page, "Teams Premium"); chip(page, '#uses .chip[data-v="In person"]')
    assert page.inner_text("#answer .aw") == "Not known yet"                     # no verified fact: never a guess

def instrumented_page(browser, base_url, script):
    ctx = browser.new_context(viewport={"width": 1280, "height": 860}, reduced_motion="reduce")
    ctx.add_init_script(script)
    pg = ctx.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(base_url); pg.wait_for_selector("#trend .lb button", state="attached")
    return ctx, pg, errors

def v_name(pg):
    return pg.evaluate("window.AIRSTACK_DATA.tools[0].name")

TRAP = """(() => { let d; Object.defineProperty(window, 'AIRSTACK_DATA', { configurable: true, get: () => d, set: v => { d = v; (%s)(v); } }); })();"""

def test_j17_an_expired_answer_is_never_shown_as_current(browser, base_url):
    ctx, pg, errors = instrumented_page(browser, base_url, "(() => { const n = Date.now, off = 60 * 864e5; Date.now = () => n() + off; })();")
    checker(pg, "Fathom")
    a = pg.inner_text("#answer")
    assert pg.inner_text("#answer .aw") == "Recheck due" and "You can stop paying" not in a and "Last verified answer:" in a and "Monitoring recheck due" in pg.inner_text("#answer .aline") and "Monitoring active" not in a and "previous answer remains as history" in a   # never current
    view(pg, "how"); pg.wait_for_selector("#cover tbody tr")
    assert "Retire ·" not in pg.inner_text("#cover") and "Recheck due" in pg.inner_text("#cover")
    assert not errors; ctx.close()

def test_j18_an_unresolved_answer_never_renders_as_keep(browser, base_url):
    mut = "v => { const k = v.tools[0].key; const a = Object.assign({}, v.pool[v.answers[k]['Business Standard'].Android], {action: 'unknown', line: 'Not enough evidence yet.', reason: 'No verified, effective source yet for: With Business Standard.', basis: null}); v.pool.push(a); v.answers[k]['Business Standard'].Android = v.pool.length - 1; }"
    ctx, pg, errors = instrumented_page(browser, base_url, TRAP % mut)
    checker(pg, v_name(pg), meeting="In person", device="Android")
    assert pg.inner_text("#answer .aw") == "Not known yet"
    assert "Keep" not in pg.inner_text("#answer .ahead") and "Retire" not in pg.inner_text("#answer .ahead")
    assert not errors; ctx.close()

def test_j19_an_unseen_product_works_through_the_same_path(browser, base_url):
    mut = """v => { v.tools.push({key: 'zz-notes', name: 'Zed Notes', cat: 'Meeting notes', aliases: []}); v.index.push(['zz-notes', 'Zed Notes', 'meeting-notes']);
                    v.answers['zz-notes'] = JSON.parse(JSON.stringify(v.answers.fireflies));
                    v.pool.push(Object.assign({}, v.pool[v.answers.fireflies['Business Standard'].Android], {reason: 'Answered from Zed Notes own record.'}));
                    v.answers['zz-notes']['Business Standard'].Android = v.pool.length - 1; }"""
    ctx, pg, errors = instrumented_page(browser, base_url, TRAP % mut)
    checker(pg, "Zed Notes", meeting="In person", device="Android")
    assert "Answered from Zed Notes own record." in pg.inner_text("#answer")      # the selected product scopes the answer (X01)
    pg.click("#change"); checker(pg, "Fireflies")
    chip(pg, '#uses .chip[data-v="In person"]'); chip(pg, '#devices .chip[data-v="Android"]')
    assert "Zed Notes" not in pg.inner_text("#answer")
    assert not errors; ctx.close()

def test_j20_task_a_zoom_user_gets_a_sourced_answer_in_four_interactions(page):
    page.wait_for_selector('#trend .lb button')
    interactions = 0
    pick(page, "Fathom"); interactions += 1                                       # type the name, Enter: one interaction
    page.wait_for_selector("#setup"); page.click("#setup"); interactions += 1                                  # Your setup · Change shows the choices
    chip(page, '#platforms .chip[data-v="Zoom"]'); interactions += 1
    chip(page, '#plans .chip[data-v="Zoom Workplace paid plan"]'); interactions += 1   # Online is already the default
    a = page.inner_text("#answer")
    assert interactions <= 4 and page.inner_text("#answer .aw") in ("Retire", "Keep", "Not known yet", "Notes covered")
    assert page.locator("#answer a.ext").count() >= 1 and "THIS CHANGES IF" in a.upper() and "fathom lists" in page.inner_text("#profile").lower()

def test_j21_same_app_and_plan_different_needs_different_answers(page):
    """Release test from the review: two users with the same app and plan but different needs get different answers."""
    page.wait_for_selector("#vendors tbody tr", state="attached")
    checker(page, "Fireflies")
    assert page.inner_text("#answer .aw") == "Notes covered" and "FIREFLIES" in page.inner_text("#answer .aline").upper() and "BUSINESS STANDARD" in page.inner_text("#setup").upper()   # every result names its app and scenario
    chip(page, '#needs .chip[data-n="none"]')
    assert page.inner_text("#answer .aw") == "Retire"
    chip(page, '#needs .chip[data-n="none"]'); chip(page, '#needs .chip[data-n="lang"]')
    assert page.inner_text("#answer .aw") == "Keep" and "8 languages" in page.inner_text("#answer .areason")
    checker(page, "tl;dv"); chip(page, '#needs .chip[data-n^="int:"] >> nth=0')      # an integration its own pages list
    assert page.inner_text("#answer .aw") == "Not known yet"                         # an unverified need is unresolved, never a pass
    page.fill("#q", "Qzzv Ledger"); page.keyboard.press("Enter")
    assert page.is_hidden("#answer") and "don’t track" in page.inner_text("#nfText")   # no unrelated answer left on screen

def test_j43_the_answer_copies_as_a_brief_with_its_plan_its_sources_and_its_dates(browser, base_url):
    """AS-242: a buyer pastes the answer into a note or a ticket. The brief is the same object the card shows."""
    origin = re.match(r"https?://[^/]+", base_url).group(0)
    ctx = browser.new_context(viewport={"width": 1280, "height": 860}, service_workers="block", reduced_motion="reduce")
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
    pg = ctx.new_page(); errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(base_url); pg.wait_for_selector("#trend .lb button", state="attached")
    checker(pg, "Otter"); plan(pg, "Zoom Workplace paid plan")
    word, reason = pg.inner_text("#answer .aw"), pg.inner_text("#answer .areason")
    pg.click("#copyBrief"); until(pg, "document.getElementById('copyBrief').textContent === 'Copied'", 4000)
    b = pg.evaluate("navigator.clipboard.readText()")
    assert b.startswith("AirStack · Otter") and "You have: Zoom Workplace paid plan, online meetings" in b, b[:200]
    assert f"Answer: {word}. {reason}" in b and "This changes if:" in b and "monitoring active through" in b
    assert re.search(r"^- .+: https://\S+ \(checked \d", b, re.M), "every source with its link and date"
    assert 'assess {"app":"Otter","plan":"Zoom Workplace paid plan","meeting":"online"}' in b and "#app=otter" in b
    assert not errors; ctx.close()

def test_j46_the_example_request_and_recorded_answer_use_the_same_words(browser, base_url):
    """The local MCP example and displayed answer come from the same reviewed record."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    pg.evaluate("document.querySelector('#tab-exec').click()")
    shown = pg.inner_text("#p-exec #mcp ~ dl.kv")
    served = pg.evaluate("""() => { const a = window.AIRSTACK_DATA.execution.mcp.request.params.arguments, D = window.AIRSTACK_DATA;
                                   return D.pool[D.answers.fireflies[a.plan][a.device]] }""")
    assert served["reason"] in shown and served["changesIf"] in shown and "Re-verified" not in shown
    assert not errors; ctx.close()

def test_j60_a_stack_is_kept_on_this_device_carried_in_a_link_and_filters_what_changed(browser, base_url):
    """AS-283: track tools from their pages; My stack shows what AirStack knows about each; nothing is sent; a link carries the stack
    to someone else, who sees it as shared until they save it; What changed can narrow to the stack."""
    origin = re.match(r"https?://[^/]+", base_url).group(0)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, service_workers="block", reduced_motion="reduce")
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
    pg = ctx.new_page(); errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(base_url); pg.wait_for_selector("#trend .lb button", state="attached"); until(pg, "!!window.AIRSTACK_MARKET")
    assert pg.is_visible("#mystack") and "No tools added yet" in pg.inner_text("#stackSum")
    assert "never sent to AirStack" in pg.inner_text("#stackNote") and "No account or server sync" in pg.inner_text("#stackNote")
    pg.click("#stackAdd"); until(pg, "document.activeElement.id === 'q'")
    sent = []; pg.on("request", lambda r: sent.append(r.url) if r.method != "GET" or "stack=" in r.url or "fireflies" in r.url.lower() else None)   # nothing about the stack ever leaves
    for name in ("Fireflies", "Notion"):
        pick(pg, name); pg.wait_for_selector("#starBtn:not([hidden])"); pg.click("#starBtn")
        assert pg.get_attribute("#starBtn", "aria-pressed") == "true"
    pg.click("#change"); pg.wait_for_selector("#mystack:not([hidden])")
    assert pg.locator("#stackList li").count() == 2 and "Scope: 2 tools" in pg.inner_text("#stackSum")
    assert pg.is_visible("#stackIntel") and pg.locator("#stackIntel .stack-insight").count() == 3
    intel = pg.inner_text("#stackIntel")
    low = intel.lower()
    assert all(x in low for x in ("monitoring", "public momentum", "review recommendation", "review order reflects evidence coverage, not product fit"))
    assert "tracked locally" in low and ("against its own 4-week level" in low or "no comparable signal" in low)
    assert "saved in this browser only" in pg.inner_text("#stackNote") and sent == []
    assert pg.get_attribute("#stackActs a[href^='#compare=']", "href") == "#compare=fireflies,notion"
    pg.click("#stackShare"); link = pg.evaluate("navigator.clipboard.readText()")
    assert "#stack=" in link
    pg2 = browser.new_context(viewport={"width": 1280, "height": 900}, service_workers="block").new_page()
    pg2.goto(base_url.split("#")[0] + "#" + link.split("#", 1)[1]); pg2.wait_for_selector("#mystack:not([hidden])")
    assert pg2.inner_text("#stackHead") == "A shared software stack" and pg2.locator("#stackList li").count() == 2
    pg2.click("#stackSave"); pg2.wait_for_selector("#stackShare")
    assert pg2.evaluate("JSON.parse(localStorage.getItem('airstack.stack.v1')).length") == 2
    pg.evaluate("document.querySelector('#news').scrollIntoView()"); pg.wait_for_selector("#newsKinds .chip[data-mine]")
    pg.click("#newsKinds .chip[data-mine]"); ids = {"fireflies", "notion"}
    names = [r.query_selector(".who b").inner_text() for r in pg.query_selector_all("#newsList .nrow")]
    assert all(n in ("Fireflies", "Notion") for n in names)
    pg.click('#stackList [data-unstack="notion"]'); assert pg.locator("#stackList li").count() == 1
    assert not errors; ctx.close(); pg2.context.close()

def test_j63_a_shared_answer_reopens_the_same_scenario_and_the_page_has_a_skip_link(browser, base_url):
    """AS-318: an answer's plan, meeting, device and needs travel in its link; opening the link shows the same answer. AS-317: the first
    Tab lands on "Skip to content"."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    pg.keyboard.press("Tab"); assert pg.evaluate("document.activeElement.className") == "skip"
    checker(pg, "Fireflies", meeting="In person", device="Android"); plan(pg, "Business Starter")
    word, scen = pg.inner_text("#answer .aw"), pg.inner_text("#setup")
    h = pg.evaluate("location.hash"); assert "plan=Business+Starter" in h and "use=in-person" in h and "device=Android" in h
    ctx2 = browser.new_context(viewport={"width": 1280, "height": 900}, service_workers="block", reduced_motion="reduce"); pg2 = ctx2.new_page()
    errors2 = []; pg2.on("pageerror", lambda e: errors2.append(str(e)))
    pg2.goto(base_url.split("#")[0] + h); pg2.wait_for_selector("#answer .aw")                                  # the link a colleague pastes
    assert pg2.inner_text("#answer .aw") == word and pg2.inner_text("#setup") == scen
    assert not errors and not errors2; ctx.close(); ctx2.close()

def test_j76_an_answer_shows_each_lines_quote_lists_what_would_close_it_and_shows_coverage_before_and_after_a_change(browser, base_url):
    """AS-346: hovering or focusing a coverage line shows its quote and page; opening a line not yet covered lists what would close it;
    Current / Proposed shows the same coverage for another plan on your platform, and the address carries the switch."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    checker(pg, "Fathom"); chip(pg, '#plans .chip[data-v="Business Starter"]')
    pg.click("#answer .how summary")                                                        # the diagram and its quotes sit behind How we decided
    line = pg.locator("#answer .needs li .ln").first
    assert pg.is_hidden("#answer .tip")
    line.hover(); assert pg.is_visible("#answer .tip") and "Take notes for me" in pg.inner_text("#answer .tip") and pg.locator("#answer .tip a").count() == 1
    pg.mouse.move(0, 0); assert pg.is_hidden("#answer .tip")
    line.focus(); assert pg.is_visible("#answer .tip")                                      # the same content for a keyboard
    assert pg.is_hidden("#answer .tip .close"); pg.keyboard.press("Enter")
    assert line.get_attribute("aria-expanded") == "true" and "What would close it" in pg.inner_text("#answer .tip") and "Google adds Business Starter" in pg.inner_text("#answer .tip")
    pg.keyboard.press("Escape"); assert line.get_attribute("aria-expanded") == "false"
    before = pg.inner_text("#answer .aw")
    pg.select_option("#swTo", "Business Standard")
    assert pg.inner_text("#answer .aw") != before and "IF YOU CHANGED TO" in pg.inner_text("#setup").upper() and "Business Standard" in pg.inner_text("#answer .cmap")
    h = pg.evaluate("location.hash"); assert "to=Business+Standard" in h and "side=proposed" in h and "plan=Business+Starter" in h
    pg.click("#swCur"); assert pg.inner_text("#answer .aw") == before and "Business Starter" in pg.inner_text("#answer .cmap")
    chip(pg, '#plans .chip[data-v="Business Standard"]'); chip(pg, '#needs .chip[data-n^="int:"]')               # a need with no evidence draws hollow
    hollow = pg.locator("#answer .needs li.unknown .ln"); assert hollow.count() == 1
    hollow.click(); assert "A page that states it, with its quote." in pg.inner_text("#answer .tip .close")
    assert not errors; ctx.close()

def test_j77_back_and_forward_restore_each_step_of_an_assessment(browser, base_url):
    """AS-346: every change of plan or need is a step in the history; back and forward restore the same scenario, and the first step restores the assumed one."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    checker(pg, "Fireflies"); assert "ASSUMING" in pg.inner_text("#setup").upper()
    chip(pg, '#plans .chip[data-v="Business Starter"]'); chip(pg, '#plans .chip[data-v="Business Plus"]'); chip(pg, '#needs .chip[data-n="none"]')
    scen = pg.inner_text("#setup"); h = pg.evaluate("location.hash"); assert "BUSINESS PLUS" in scen.upper() and "needs=none" in h
    pg.go_back(); pg.wait_for_function("!location.hash.includes('needs=') && document.querySelector('#setup').textContent.includes('Business Plus')")
    pg.go_back(); pg.wait_for_function("document.querySelector('#setup').textContent.includes('Business Starter')")
    pg.go_back(); pg.wait_for_function("document.querySelector('#setup').textContent.toUpperCase().includes('ASSUMING')")
    pg.go_forward(); pg.go_forward(); pg.go_forward()
    pg.wait_for_function("location.hash.includes('needs=none')"); assert pg.inner_text("#setup") == scen and pg.evaluate("location.hash") == h
    assert not errors; ctx.close()

def add_to_compare(pg, name):
    """Type into the comparison's own search and take the first match with the keyboard."""
    pg.fill("#cmpQ", name); pg.wait_for_selector("#cmpTa li[data-i]"); pg.press("#cmpQ", "Enter")

def test_j78_compare_puts_two_to_five_products_side_by_side_each_cell_in_the_pages_words(browser, base_url):
    """AS-346, AS-366: a comparison of 2 to 5 products opened from an answer, every cell a quote found on its page (with the page and the day) or Not observed; the
    address carries it, back and forward restore it, and a saved one shows its monitoring window."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    checker(pg, "Fathom"); pg.click("#answer [data-compare]"); pg.wait_for_selector("#cmpQ"); until(pg, "document.querySelector('#cmpSub').textContent.includes('2 to 5')")
    assert pg.evaluate("location.hash") == "#compare=fathom" and "2 to 5" in pg.inner_text("#cmpSub") and pg.locator("#cmpTbl").count() == 0
    add_to_compare(pg, "Otter"); pg.wait_for_selector("#cmpTbl")
    assert pg.evaluate("location.hash") == "#compare=fathom,otter" and pg.evaluate("document.body.dataset.view") == "compare"
    assert re.search(r"Scope: 2 products × \d+ fields · Coverage: \d+ of \d+ cells sourced", pg.inner_text("#cmpSub"))
    facts = pg.evaluate("fetch('chain-data.json').then(r => r.json())")["entities"]
    rows = pg.locator("#cmpTbl tbody tr")
    assert rows.count() >= 3
    for r in range(rows.count()):
        for c, e in enumerate(("fathom", "otter")):
            td = rows.nth(r).locator("td").nth(c); quotes = {f["quote"] for f in facts[e]["facts"] if f["verified"]}
            if td.inner_text().strip() == "Not observed": continue
            label = rows.nth(r).locator("th").inner_text()
            if label.startswith("List price"): assert td.locator("a.ext").count() == 1 and "found" in td.inner_text(); continue
            assert td.locator("a.ext").count() >= 1 and "found" in td.inner_text() and td.locator("q").count() >= 1, (label, td.inner_text())
            for q in td.locator("q").all(): assert q.text_content() in quotes, (label, q.text_content())     # a quote the code found on a page, never a paraphrase
    assert "Not observed" in pg.inner_text("#cmpTbl")
    for e in ("fireflies", "tldv", "read-ai"): add_to_compare(pg, e)
    assert pg.locator("#cmpQ").is_disabled() and "Five is the most" in pg.inner_text("#cmpBody")
    pg.click('[data-rm="read-ai"]'); assert pg.locator("#cmpQ").is_enabled()
    pg.click("#cmpSave"); exp = pg.inner_text("#cmpExp"); assert "Saved" in exp and re.search(r"Monitoring active through \d+ \w{3} 20\d\d", exp)
    h = pg.evaluate("location.hash"); pg.go_back(); until(pg, "document.querySelectorAll('#cmpTbl thead th').length == 6")   # back removes the last step
    pg.go_forward(); until(pg, "document.querySelectorAll('#cmpTbl thead th').length == 5")
    ctx2 = browser.new_context(viewport={"width": 1280, "height": 900}, service_workers="block", reduced_motion="reduce"); pg2 = ctx2.new_page()
    pg2.goto(base_url.split("#")[0] + h); pg2.wait_for_selector("#cmpTbl")                                              # the link a colleague pastes
    assert pg2.locator("#cmpTbl thead th").count() == 5 and "Monitoring active through" in pg2.inner_text("#cmpExp")
    assert not errors; ctx.close(); ctx2.close()

def test_j79_compare_is_one_click_from_the_first_screen_works_by_keyboard_and_on_a_phone(browser, base_url):
    """AS-366: the first screen's Compare link opens an empty comparison with examples; products are added with the keyboard alone; rows where the
    observed values differ are marked; a price shows only with its pricing page; a 390 px phone reads it without the page scrolling sideways."""
    ctx, pg, errors = _open(browser, base_url, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, reduced_motion="reduce")
    origin = re.match(r"https?://[^/]+", base_url).group(0)
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
    pg.click("#cmpGo"); pg.wait_for_selector(".cmp-eg a"); until(pg, "document.querySelector('#cmpSub').textContent.includes('2 to 5')")
    assert pg.evaluate("location.hash") == "#compare=" and "2 to 5" in pg.inner_text("#cmpSub") and pg.locator("#cmpTbl").count() == 0
    pg.focus("#cmpQ"); pg.keyboard.type("Notion"); pg.wait_for_selector("#cmpTa li[data-i]"); pg.keyboard.press("Enter")
    pg.keyboard.type("Asana"); pg.wait_for_selector("#cmpTa li[data-i]"); pg.keyboard.press("Enter"); pg.wait_for_selector("#cmpTbl")
    assert pg.evaluate("location.hash") == "#compare=notion,asana" and pg.evaluate("document.activeElement.id") == "cmpQ"
    assert pg.locator("#cmpTbl tr.diff").count() >= 1 and "differs" in pg.inner_text("#cmpTbl tr.diff")
    price = pg.locator("#cmpTbl tbody tr").first
    assert price.locator("th").inner_text().startswith("List price") and price.locator("td").first.locator("a.ext").count() == 1 and "found" in price.inner_text()
    pg.locator("#cmpTbl details.qt summary").first.click(); assert pg.locator("#cmpTbl details.qt[open] q").first.is_visible()   # tap a cell's Quote: the page's words
    pg.click("#cmpCopy"); until(pg, "document.getElementById('cmpCopy').textContent === 'Link copied'")
    assert pg.evaluate("navigator.clipboard.readText()") == pg.url
    assert pg.evaluate("document.documentElement.scrollWidth") <= 391                                                  # the table scrolls inside its box
    assert pg.evaluate("(() => { const s = document.querySelector('#cmpSec .scroll'); return s.scrollWidth <= s.clientWidth })()")   # two products fit across, field names above their cells: no sideways scrolling at all
    assert pg.evaluate("(() => { const c = [...document.querySelectorAll('#cmpTbl tbody tr:first-child td')].map(t => t.getBoundingClientRect()); return c.length == 2 && Math.abs(c[0].top - c[1].top) < 2 })()")   # side by side
    assert pg.evaluate("Math.min(...[...document.querySelectorAll('#cmpTbl td *, #cmpTbl tbody th')].filter(e => e.offsetParent && [...e.childNodes].some(n => n.nodeType == 3 && n.textContent.trim())).map(e => parseFloat(getComputedStyle(e).fontSize)))") >= 14   # readable
    pg.click("#cmpDiff"); assert pg.locator("#cmpTbl tbody tr:not(.diff)").count() == 0; pg.click("#cmpDiff")
    add_to_compare(pg, "Linear"); pg.wait_for_selector("#cmpTbl:not(.two)")                                            # three or more scroll in their box, field names pinned
    assert pg.is_visible(".cmp-swipe") and "every product" in pg.inner_text(".cmp-swipe")
    assert pg.evaluate("getComputedStyle(document.querySelector('#cmpTbl tbody th')).position") == "sticky" and pg.evaluate("document.documentElement.scrollWidth") <= 391
    pg.go_back(); until(pg, "document.querySelectorAll('#cmpTbl thead th').length == 3")
    pg.go_back(); until(pg, "document.querySelectorAll('#cmpChips .cpick').length == 1 && !document.querySelector('#cmpTbl')")   # back removes the last step
    assert not errors; ctx.close()
