# spec: AS-331
import functools, http.server, pathlib, pytest, re, socketserver, threading
from playwright import sync_api as pw                                   # required: a missing browser fails the journeys, never skips them (AS-331)
from .journey_kit import ROOT, _open

SITE = None                                                              # the assembled site the journeys serve (set by base_url)

def _star_headers():
    block = re.search(r"(?m)^/\*\n((?:[ \t]+.+\n?)+)", ((SITE or ROOT / "web" / "public") / "_headers").read_text()).group(1)
    return [tuple(x.strip() for x in l.split(":", 1)) for l in block.splitlines() if l.strip()]

class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self):                                               # the headers production sends (the /* block of _headers, CSP included): a local run must not be kinder than the real thing
        for name, value in _star_headers():
            self.send_header(name, value)
        super().end_headers()

@pytest.fixture(scope="session")
def base_url():
    import os
    if os.environ.get("AIRSTACK_BASE_URL"):                              # run every journey against a deployed site
        yield os.environ["AIRSTACK_BASE_URL"]
        return
    import subprocess, tempfile
    site = pathlib.Path(tempfile.mkdtemp(prefix="airstack-site-"))
    subprocess.run([str(ROOT / "tools" / "assemble.sh"), str(site)], check=True)   # the site exactly as deploy.sh ships it
    global SITE; SITE = site                                                         # and its headers, the CSP included
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(site)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/index.html"
    srv.shutdown()

@pytest.fixture(scope="session")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome", headless=True)       # the installed Chrome; no browser download
        except Exception:
            b = p.chromium.launch(headless=True)
        yield b
        b.close()

@pytest.fixture
def page(browser, base_url):
    ctx, pg, errors = _open(browser, base_url, reduced_motion="reduce")
    yield pg
    assert not errors, errors
    ctx.close()
