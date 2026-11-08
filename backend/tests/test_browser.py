"""The assembled site in real Chrome: every primary view opens without errors and fits a phone."""
import functools
import http.server
import pathlib
import re
import socketserver
import subprocess
import threading
import time
import pytest
from playwright import sync_api as playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
SITE = None


def wait(page, expression, timeout=30_000):
    end = time.monotonic() + timeout / 1000
    while not page.evaluate(expression):
        assert time.monotonic() < end, f"timed out: {expression}"
        page.wait_for_timeout(50)


def headers():
    text = (SITE / "_headers").read_text()
    block = re.search(r"(?m)^/\*\n((?:[ \t]+.+\n?)+)", text).group(1)
    return [tuple(part.strip() for part in line.split(":", 1)) for line in block.splitlines() if line.strip()]


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def end_headers(self):
        for name, value in headers():
            self.send_header(name, value)
        super().end_headers()


@pytest.fixture(scope="session")
def app_url(tmp_path_factory):
    global SITE
    SITE = tmp_path_factory.mktemp("site")
    subprocess.run([str(ROOT / "tools" / "assemble.sh"), str(SITE)], check=True)
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(SITE)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()


@pytest.fixture(scope="session")
def chrome():
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = runtime.chromium.launch(headless=True)
        yield browser
        browser.close()


def open_app(chrome, app_url, width=1280):
    context = chrome.new_context(viewport={"width": width, "height": 900}, reduced_motion="reduce")
    page, errors = context.new_page(), []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(app_url)
    page.wait_for_selector("#trend .lb button", state="attached")
    return context, page, errors


def comparison_pair(page):
    return page.evaluate("window.AIRSTACK_DATA.index.slice(0, 2).map(row => ({id: row[0], name: row[1]}))")


FITS = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"


@pytest.mark.parametrize("width", [1280, 390])
def test_primary_views_open_without_browser_errors_and_fit(chrome, app_url, width):
    context, page, errors = open_app(chrome, app_url, width)
    for view in ("markets", "insights", "calendar", "makers", "compare", "overview"):
        page.evaluate("view => { location.hash = view === 'overview' ? '#/' : '#/' + view }", view)
        page.wait_for_selector(f'.nav a[data-view="{view}"][aria-current="page"]', state="attached")
        assert page.evaluate(FITS), view
    assert not page.query_selector('.nav a[data-view="agents"]')
    page.evaluate("location.hash = '#/agents'")
    page.wait_for_function("document.body.dataset.view === 'agents'")
    assert not errors
    context.close()


def test_stack_stays_local_and_starts_a_comparison(chrome, app_url):
    context, page, errors = open_app(chrome, app_url)
    pair = comparison_pair(page)
    assert page.evaluate("localStorage.getItem('airstack.stack.v1')") is None
    for item in pair:
        page.fill("#q", item["name"])
        page.press("#q", "Enter")
        page.wait_for_selector("#starBtn:not([hidden])")
        page.click("#starBtn")
        page.click("#change")
    saved = page.evaluate("JSON.parse(localStorage.getItem('airstack.stack.v1'))")
    ids = [item["id"] for item in pair]
    assert [item["id"] for item in saved] == ids
    assert page.get_attribute("#stackActs a[href^='#compare=']", "href") == "#compare=" + ",".join(ids)
    assert not errors
    context.close()
    other, fresh, other_errors = open_app(chrome, app_url)
    assert fresh.evaluate("localStorage.getItem('airstack.stack.v1')") is None
    assert not other_errors
    other.close()


def test_signal_tiles_fit_their_container(chrome, app_url):
    context, page, errors = open_app(chrome, app_url)
    page.locator("#trend .lb button").first.click()
    page.wait_for_selector("#toolcard .tiles")
    assert page.locator("#toolcard .tile").evaluate_all(
        "tiles => tiles.every(tile => tile.scrollWidth <= tile.clientWidth && [...tile.children].every(child => child.getBoundingClientRect().right <= tile.getBoundingClientRect().right + 1))"
    )
    assert page.evaluate(FITS)
    assert not errors
    context.close()


def test_calendar_separates_records_schedules_and_unconfirmed_dates(chrome, app_url):
    context, page, errors = open_app(chrome, app_url)
    page.evaluate("location.hash = '#/calendar'")
    page.wait_for_selector('.nav a[data-view="calendar"][aria-current="page"]')
    wait(page, "document.querySelectorAll('#calendar a.ext').length > 0")
    assert "repeating-linear-gradient" in page.locator(".clegend .u").evaluate("node => getComputedStyle(node).backgroundImage")
    assert all(link.startswith("https://") for link in page.locator("#calendar a.ext").evaluate_all("xs => xs.map(x => x.href)"))
    assert not errors
    context.close()


def test_compare_remains_usable_on_a_phone(chrome, app_url):
    context, page, errors = open_app(chrome, app_url, width=390)
    ids = [item["id"] for item in comparison_pair(page)]
    page.evaluate("ids => { location.hash = '#compare=' + ids.join(',') }", ids)
    page.wait_for_selector('.nav a[data-view="compare"][aria-current="page"]')
    wait(page, "document.querySelectorAll('#cmpTbl thead th').length >= 3")
    assert page.evaluate(FITS)
    assert page.locator("#cmpTbl").is_visible()
    assert not errors
    context.close()
