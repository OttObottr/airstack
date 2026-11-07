# spec: AS-331
import pathlib, time

ROOT = pathlib.Path(__file__).resolve().parents[1]

def until(pg, expr, timeout=30000):
    """Wait for a page expression to be truthy. Polls with evaluate, because wait_for_function evals its string, which the page's CSP (no unsafe-eval) rightly refuses."""
    end = time.monotonic() + timeout / 1000
    while not pg.evaluate(expr):
        assert time.monotonic() < end, f"timed out waiting for: {expr[:140]}"
        pg.wait_for_timeout(50)

def view(pg, v):
    """Open a view by its route (#/markets), as the tabs do, and wait until it is the current one (AS-260)."""
    pg.evaluate("v => { location.hash = v === 'overview' ? '#/' : '#/' + v }", v)
    pg.wait_for_selector(f'.nav a[data-view="{v}"][aria-current="page"]')

def _open(browser, base_url, **ctx_kw):
    ctx = browser.new_context(**({"viewport": {"width": 1280, "height": 860}} | ctx_kw))
    pg = ctx.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(base_url); pg.wait_for_selector("#trend .lb button", state="attached")
    return ctx, pg, errors

DATA = "() => window.AIRSTACK_DATA"

SMALL_TEXT = """() => [...document.querySelectorAll('body *')].filter(e => e.offsetParent !== null && !e.classList.contains('sr')
    && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()))
    .filter(e => parseFloat(getComputedStyle(e).fontSize) < 12).map(e => e.tagName + ':' + e.textContent.trim().slice(0, 30))"""

def pick(pg, name):
    """Search the way a person does: type the tool's name and press Enter. Nothing is preselected for them. Search lives in Overview."""
    if not pg.locator("#q").is_visible(): view(pg, "overview")
    pg.fill("#q", name); pg.press("#q", "Enter"); pg.wait_for_selector("#picked:not([hidden])")

def platform_of(name):
    return "Zoom" if name.startswith("Zoom") else "Microsoft" if name in ("Teams without Premium", "Teams Premium", "Microsoft Copilot") else "Google"

def chip(pg, sel):
    """Click a setup chip (plan, platform, meeting, device, need): the choices sit behind 'Your setup · Change', so open it first when it is closed (AS-102)."""
    target = pg.locator(sel).first
    if not target.is_visible():
        if pg.get_attribute("#setup", "aria-expanded") == "true": pg.click("#setup")   # reset a half-rendered/open state before opening deterministically
        pg.click("#setup")
    target.wait_for(state="visible")
    target.click()

def plan(pg, name):
    """Plans are grouped under a platform: pick the platform first (one extra click), then the plan."""
    chip(pg, f'#platforms .chip[data-v="{platform_of(name)}"]'); chip(pg, f'#plans .chip[data-v="{name}"]')
