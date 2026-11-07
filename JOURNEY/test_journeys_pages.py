# spec: AS-136 AS-252 AS-268 AS-316 AS-317 AS-318 AS-319 AS-350
import json, re
from .journey_kit import DATA, _open, pick, until, view


def test_j42_anyone_can_run_airstack_locally_from_two_copyable_commands(browser, base_url):
    """AS-136: the public release gives agents a local, read-only MCP setup without exposing a billable hosted endpoint."""
    origin = re.match(r"https?://[^/]+", base_url).group(0)
    ctx = browser.new_context(viewport={"width": 1280, "height": 860}, service_workers="block", reduced_motion="reduce")
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
    pg = ctx.new_page(); errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(base_url); pg.wait_for_selector("#trend .lb button", state="attached"); view(pg, "agents")
    assert pg.locator("#agents").is_visible()
    assert pg.evaluate("document.querySelector('#agTools').textContent === AIRSTACK_DATA.execution.mcp.tools.join(', ')")
    assert pg.evaluate("document.getElementById('agScope').textContent.includes(AIRSTACK_DATA.execution.mcp.tools.length + ' reviewed tools')")
    assert "Clone, start locally" in pg.inner_text("#agScope") and "verified" in pg.inner_text("#agScope")
    pg.click("[data-copy='#agCli']"); until(pg, "document.querySelector(\"[data-copy='#agCli']\").textContent === 'Copied'", 4000)
    assert pg.evaluate("navigator.clipboard.readText()") == "PYTHONPATH=backend python -m airstack.mcp_server data/airstack-demo.db"
    pg.click("[data-copy='#agJson']"); until(pg, "document.querySelector(\"[data-copy='#agJson']\").textContent === 'Copied'", 4000)
    assert json.loads(pg.evaluate("navigator.clipboard.readText()")) == {
        "mcpServers": {"airstack": {"command": "python", "args": ["-m", "airstack.mcp_server", "data/airstack-demo.db"], "env": {"PYTHONPATH": "backend"}}}
    }
    assert pg.locator("#agents a[href*='docs/MCP.md']").count() == 1
    pick(pg, "OpenRouter"); pg.wait_for_selector("#toolcard .tiles")
    pg.click("#mcpLink"); pg.wait_for_selector('.nav a[data-view="agents"][aria-current="page"]')   # one click from any product to the Agents view
    assert pg.locator("#agents").is_visible() and pg.evaluate("Math.abs(document.getElementById('agents').getBoundingClientRect().top) < 120")
    assert not errors; ctx.close()

def test_j45_the_daily_brief_says_who_wrote_it_and_every_number_in_it_is_in_a_figure_it_cites(browser, base_url):
    """The brief publishes only grounded figures and appears on the landing page."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    B = pg.evaluate("window.AIRSTACK_DATA.brief")
    if not B:
        assert pg.locator("#brief").is_hidden(); ctx.close(); return                 # no brief yet: nothing pretends to be one
    assert pg.inner_text("#briefT") == "Latest evidence brief" and B["date"][:4] in pg.inner_text("#briefSub")
    assert pg.locator("#brief").is_visible() and "Written by Muse Wonder" in pg.inner_text("#briefSub") and "checked every number" in pg.inner_text("#briefSub")
    nums = lambda t: set(n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", t))
    for it in B["items"]:
        assert nums(it["text"]) <= set().union(*(nums(B["facts"][c]["text"]) for c in it["cites"])), it
    assert len(pg.query_selector_all("#briefItems li")) == len(B["items"])
    pick(pg, "Pinecone"); pg.wait_for_selector("#toolcard .tiles")
    assert not pg.locator("#brief").is_visible()                                       # a tool's page is about that tool
    assert not errors; ctx.close()

def test_j51_a_products_static_page_is_readable_without_javascript_and_links_back_to_the_app(browser, base_url):
    """AS-252: /p/notion/ is plain HTML a crawler or an answer engine can read and cite; its button opens the live answer."""
    root = base_url.rsplit("/", 1)[0] + "/" if base_url.endswith(".html") else base_url
    ctx = browser.new_context(java_script_enabled=False); pg = ctx.new_page(); pg.goto(root + "p/notion/")
    assert pg.title().startswith("Notion:") and pg.locator("h1").inner_text() == "Notion"
    assert pg.locator('link[rel="canonical"]').get_attribute("href") == "https://airstack.bot/p/notion/"
    assert pg.locator('a.cta').get_attribute("href") == "/#app=notion" and pg.locator("table").count() >= 1
    ctx.close()

def test_j59_how_it_works_is_a_methodology_page_built_from_the_examples_own_records(browser, base_url):
    """AS-268: one line, then four steps each with real evidence from the worked example (its page, its exact words, the judge's receipt,
    its monitoring status), then the replay, the market, the record and the fine print; no spend figure anywhere."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    view(pg, "how"); pg.wait_for_selector("#pipe li")
    D = pg.evaluate(DATA)
    assert pg.inner_text("#methodT") == "Every answer carries its evidence and monitoring status."
    steps = pg.query_selector_all("#pipe li"); assert len(steps) == 4
    launch = next(s for s in D["sources"] if s["source"] == "Google Workspace Updates" and s["real"])
    assert launch["expect"] in steps[1].inner_text()                                                  # the page's own words, as code found them
    a = D["pool"][D["answers"]["fireflies"]["Business Standard"]["Android"]]
    assert D["meta"]["model"] in steps[2].inner_text() and "tokens" in steps[2].inner_text()
    assert "Verified through" in steps[3].inner_text()
    order = pg.evaluate("[...document.querySelectorAll('section[data-views~=\"how\"]:not([hidden])')].map(s => s.id)")
    assert order[:2] == ["method", "life"] and order[-1] == "fineprint" and "detail" in order
    assert not re.search(r"\$\s?\d", pg.inner_text("main")), "no spend figure on the page"
    assert len(pg.query_selector_all("#fine li")) >= 4
    assert not errors; ctx.close()

def test_j61_terms_and_privacy_are_one_short_page_linked_from_every_view(browser, base_url):
    """AS-316: the footer links a short terms and privacy page; it promises little and says what is true about data."""
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    href = pg.get_attribute(".foot a[href='/legal/']", "href"); assert href == "/legal/"
    root = re.match(r"https?://[^/]+", base_url).group(0)
    pg.goto(root + "/legal/"); body = pg.inner_text("main")
    assert pg.title().startswith("Terms and privacy") and "as is" in body and "not advice" in body and "No account is required" in body
    assert len(body.split()) < 90                                                                                      # short on purpose: fewer words, fewer promises
    assert pg.locator("a[href$='NOTICE.md']").count() == 1                                                            # sources and licences, one link
    pg.goto(root + "/legal/notices.txt"); notices = pg.inner_text("body")
    assert all(w in notices for w in ("Lucide", "endoflife.date", "Community Data License Agreement")) and "Tailwind" not in notices and "d3-hierarchy" not in notices   # the page ships no third-party code but its icons
    assert not errors; ctx.close()

def test_j65_a_makers_page_is_readable_without_javascript_and_links_its_products(browser, base_url):
    """AS-317: /o/<maker>/ is plain HTML a crawler or an answer engine can read and cite: who it is, its products, where to find it."""
    root = re.match(r"https?://[^/]+", base_url).group(0)
    ctx = browser.new_context(java_script_enabled=False); pg = ctx.new_page(); pg.goto(root + "/o/figma-inc/")
    assert pg.locator("h1").inner_text() == "Figma Inc" and pg.title().endswith("· AirStack")
    assert pg.locator('a[href="/p/figma/"]').count() == 1 and pg.locator('a.cta').get_attribute("href") == "/#app=figma-inc"
    ld = json.loads(pg.locator('script[type="application/ld+json"]').first.text_content())
    assert ld["@type"] == "Organization" and ld["url"] == "https://airstack.bot/o/figma-inc/"
    ctx.close()

def test_j66_a_category_page_is_readable_without_javascript_with_its_products_and_sourced_prices(browser, base_url):
    """AS-318: /c/crm-sales/ is plain HTML: why teams use it, the category in numbers, and every product with its quoted starting price."""
    root = re.match(r"https?://[^/]+", base_url).group(0)
    ctx = browser.new_context(java_script_enabled=False); pg = ctx.new_page(); pg.goto(root + "/c/crm-sales/")
    assert pg.locator("h1").inner_text() == "CRM and sales" and "Why teams use it" in pg.inner_text("main")
    assert pg.locator('td a[href^="/p/"]').count() >= 20 and "of" in pg.inner_text("table >> nth=0")
    ld = json.loads(pg.locator('script[type="application/ld+json"]').first.text_content()); assert ld["@type"] == "CollectionPage"
    ctx.close()

def test_j67_a_comparison_page_puts_two_products_own_pages_side_by_side(browser, base_url):
    """AS-319: /compare/airtable-vs-notion/ without JavaScript: each value quoted from that product's own pages, the differences stated, nothing ranked."""
    root = re.match(r"https?://[^/]+", base_url).group(0)
    ctx = browser.new_context(java_script_enabled=False); pg = ctx.new_page(); pg.goto(root + "/compare/airtable-vs-notion/")
    assert pg.locator("h1").inner_text() == "Airtable vs Notion"
    assert pg.locator('th a[href="/p/airtable/"]').count() == 1 and pg.locator('th a[href="/p/notion/"]').count() == 1
    text = pg.inner_text("main").lower(); assert "where they differ" in text and "nothing here is a ranking" in text
    pg.goto(root + "/p/notion/"); assert pg.locator('a[href="/compare/airtable-vs-notion/"]').count() == 1
    ctx.close()
