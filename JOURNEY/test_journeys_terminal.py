# spec: AS-341
from datetime import date
from .journey_kit import _open, pick, until, view


def _day(iso):
    d = date.fromisoformat(iso[:10]); return f"{d.day} {d.strftime('%b')} {d.year}"

def test_j71_the_palette_jumps_to_a_view_a_product_or_a_command_from_the_keyboard_alone(page):
    """AS-341: Ctrl/Cmd-K and `/` open one modal palette (loaded on first use); a product is found by the search's own ranking and opens with Enter; a view and a command
    are reached the same way; Escape closes it and focus returns to where it was; Tab stays inside it."""
    assert page.evaluate("document.getElementById('pal')") is None                       # nothing of it exists until it is asked for
    page.keyboard.press("Shift"); until(page, "!!window.AIRSTACK_MARKET")                 # the market file loads on first use and redraws the answer: let it finish before views are changed
    for chord in ("Control+k", "Meta+k", "/"):
        page.evaluate("document.activeElement.blur()"); page.keyboard.press(chord); page.wait_for_selector("#pal[open]")
        assert page.evaluate("document.activeElement.id") == "palq"
        assert page.get_attribute("#pal", "aria-modal") == "true" and page.get_attribute("#palq", "role") == "combobox" and page.get_attribute("#palq", "aria-label")
        for _ in range(3): page.keyboard.press("Tab")
        assert page.evaluate("!!document.activeElement.closest('#pal')")                  # focus cannot leave the dialog
        page.keyboard.press("Escape"); page.wait_for_selector("#pal", state="hidden")
    page.focus("#q"); page.keyboard.press("Control+k"); page.wait_for_selector("#pal[open]"); page.keyboard.press("Escape")
    assert page.evaluate("document.activeElement.id") == "q"                              # back where it was
    page.keyboard.press("Escape"); page.evaluate("document.activeElement.blur()")
    page.keyboard.press("/"); page.wait_for_selector("#pal[open]"); page.keyboard.type("pinec"); page.wait_for_selector("#pall li[role=option]")
    assert page.inner_text("#pall li[role=option]").startswith("Pinecone")                # the search's own first result
    act = page.get_attribute("#palq", "aria-activedescendant"); assert page.get_attribute(f"#{act}", "aria-selected") == "true"
    page.keyboard.press("Enter"); page.wait_for_selector("#pal", state="hidden")
    assert page.inner_text("#pickedName") == "Pinecone"
    page.evaluate("document.activeElement.blur()"); page.keyboard.press("/"); page.wait_for_selector("#pal[open]"); page.keyboard.type("calendar"); page.keyboard.press("Enter")
    page.wait_for_selector('.nav a[data-view="calendar"][aria-current="page"]')
    page.keyboard.press("/"); page.wait_for_selector("#pal[open]"); page.keyboard.type("open github"); assert "Open GitHub" in page.inner_text("#pall")
    page.context.route("https://github.com/**", lambda r: r.fulfill(status=200, body="ok"))   # no network needed: the tab only has to ask for the right address
    with page.context.expect_page() as opened: page.keyboard.press("Enter")                # the command runs: GitHub opens in its own tab and the palette stays closed
    opened.value.wait_for_load_state("commit"); assert opened.value.url == "https://github.com/OttObottr/airstack"
    assert page.evaluate("!document.getElementById('pal').open"); opened.value.close(); view(page, "overview")
    page.keyboard.press("/"); page.wait_for_selector("#pal[open]"); page.keyboard.type("change tool"); page.keyboard.press("Enter")
    page.wait_for_selector("#picked", state="hidden"); assert page.evaluate("document.activeElement.id") == "q"   # the command did its work and chose where focus goes

def test_j72_the_palette_fits_a_phone_and_respects_reduced_motion(browser, base_url):
    """AS-341: at 320 px the palette stays inside the screen, its rows are tap-sized, and nothing in it animates."""
    ctx, pg, errors = _open(browser, base_url, viewport={"width": 320, "height": 640}, reduced_motion="reduce")
    wide = pg.evaluate("document.documentElement.scrollWidth")                          # whatever width the page itself has at 320
    pg.keyboard.press("/"); pg.wait_for_selector("#pal[open]"); pg.keyboard.type("m")
    b = pg.query_selector("#pal").bounding_box()
    assert b["x"] >= 0 and b["x"] + b["width"] <= 320 and pg.evaluate("document.documentElement.scrollWidth") == wide
    boxes = [b for e in pg.query_selector_all("#pal li, #pal input, #pal button") if (b := e.bounding_box())]
    assert boxes and all(b["x"] + b["width"] <= 320 for b in boxes)                         # hidden filtered rows have no geometry
    assert pg.query_selector("#pall li[role=option]").bounding_box()["height"] >= 44
    assert pg.evaluate("getComputedStyle(document.querySelector('#pal')).animationName") == "none"
    assert not errors; ctx.close()

def test_j73_the_status_bar_dates_come_from_the_data_files_and_the_tape_can_show_only_your_tools(browser, base_url):
    """AS-341: each source in the palette's status bar shows the date its own data file records; a file that records none says Not observed;
    the tape can be narrowed to the tools you track, and back."""
    ctx = browser.new_context(viewport={"width": 1280, "height": 860}, service_workers="block", reduced_motion="reduce")
    ctx.route("**/hf.json", lambda r: r.fulfill(status=200, content_type="application/json", body='{"source":{}}'))     # a file with no recorded run
    pg = ctx.new_page(); errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(base_url); pg.wait_for_selector("#trend .lb button", state="attached")
    pg.keyboard.press("Control+k"); pg.wait_for_selector("#pal[open]")
    until(pg, "![...document.querySelectorAll('.palbar li span:last-child')].some(e => e.textContent === '…')")
    got = {li.query_selector("span").inner_text(): li.query_selector("span:last-child").inner_text() for li in pg.query_selector_all(".palbar li")}
    d = pg.evaluate("[AIRSTACK_DATA.meta.checked_at, AIRSTACK_DATA.moversTop.generated, AIRSTACK_DATA.dir.fetched_at]")
    news = pg.evaluate("fetch('news.json').then(r => r.json()).then(j => j.source.read)")
    ev = pg.evaluate("fetch('events.json').then(r => r.json()).then(j => j.source.built_for)")
    assert got["Pages read for answers"] == _day(d[0]) and got["Download figures (built)"] == _day(d[1]) and got["Software directory (Wikidata)"] == _day(d[2])
    assert got["Vendor news"] == _day(news) and got["Calendar"] == _day(ev)
    assert got["Open models (Hugging Face)"] == "Not observed"
    pg.keyboard.press("Escape")
    pg.keyboard.press("Shift"); until(pg, "!!window.AIRSTACK_MARKET")             # the market file replaces the first screen's movers with the full list; the tape follows it, so pick from it
    pg.wait_for_timeout(300)
    row = pg.evaluate("(({id, name}) => ({id, name}))(AIRSTACK_MARKET.movers.rows.find(r => r.dl && r.dl.vsBase != null))"); name = row["name"]
    all_tools = pg.locator("#tape a").count()
    pg.evaluate("id => __airstack.selectTool(__airstack.byId(id))", row["id"])                 # by id: two listings can share a name
    pg.wait_for_selector("#starBtn:not([hidden])"); pg.click("#starBtn")
    pg.keyboard.press("Control+k"); pg.wait_for_selector("#pal[open]"); until(pg, "document.activeElement.closest('#pal') !== null"); pg.keyboard.type("only my")
    until(pg, "(document.querySelector('#pal [aria-selected=true]') || {}).textContent?.toLowerCase().includes('only my')")      # on a slow runner the list lags the typing: Enter only once the command is the one highlighted
    pg.keyboard.press("Enter")
    until(pg, "document.querySelector('#tape .as').textContent.startsWith('your tools')")
    assert 0 < pg.locator("#tape a").count() < all_tools and all(name in t for t in pg.locator("#tape a b").all_inner_texts())
    pg.keyboard.press("Control+k"); pg.wait_for_selector("#pal[open]"); until(pg, "document.activeElement.closest('#pal') !== null"); pg.keyboard.type("show every")
    until(pg, "(document.querySelector('#pal [aria-selected=true]') || {}).textContent?.toLowerCase().includes('show every')")      # on a slow runner the list lags the typing: Enter only once the command is the one highlighted
    pg.keyboard.press("Enter")
    until(pg, f"document.querySelectorAll('#tape a').length === {all_tools}")
    assert not errors; ctx.close()

def test_j74_j_and_k_move_through_a_list_unless_you_are_typing(page):
    """AS-341: j goes to the next row of the list you are in and k to the previous, in the trending list and in a table; typing j in a box types j."""
    page.keyboard.press("Shift"); until(page, "!!window.AIRSTACK_MARKET")                 # the market file redraws the lists when it arrives; a row focused before that would be replaced
    page.evaluate("document.activeElement.blur()"); page.keyboard.press("j")
    first = page.evaluate("document.activeElement.dataset.pick"); assert first
    page.keyboard.press("j"); second = page.evaluate("document.activeElement.dataset.pick"); assert second and second != first
    page.keyboard.press("k"); assert page.evaluate("document.activeElement.dataset.pick") == first
    page.keyboard.press("k"); assert page.evaluate("document.activeElement.dataset.pick") == first      # the top stays the top
    page.focus("#q"); page.keyboard.type("jk"); assert page.input_value("#q") == "jk" and page.evaluate("document.activeElement.id") == "q"
    view(page, "markets"); page.wait_for_selector("#mvt tbody tr"); page.evaluate("document.activeElement.blur()")
    page.keyboard.press("j"); page.keyboard.press("j")
    assert page.evaluate("[...document.querySelectorAll('#mvt tbody tr')].findIndex(r => r.contains(document.activeElement))") == 1
