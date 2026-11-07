# spec: AS-274
"""Every page AirStack reads goes through here. It sends one honest name with a contact, obeys each host's robots.txt (RFC 9309),
honours Retry-After once and caps bodies. get() returns (status, text, headers). Status 0 means no response; a page robots.txt
disallows is never requested, and comes back as (0, "", {"x-robots": "disallowed"}).

published(url) is the other half: what was read may be shown only if its host's terms allow automated reading and robots.txt did
not close the page at the last sweep (`python -m airstack.fetch --sweep` writes data/robots-disallowed.json)."""
import ipaddress, json, re, socket, sys, threading, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from . import paths

UA = "AirStackBot/1.0 (+https://airstack.bot/legal/)"
AGENT = "AirStackBot"
MAX_BYTES = 4_000_000
ROBOTS_TIMEOUT = 30
TERMS_EXCLUDED = {"apps.apple.com"}   # terms bar automated reading: never fetched, never shown
DISALLOWED = paths.ROBOTS_DISALLOWED
_robots, _lock, _closed = {}, threading.Lock(), None
_resolve = socket.getaddrinfo

class UnsafeUrl(ValueError): pass

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

_opener = urllib.request.build_opener(_NoRedirect)

def _open(req, timeout):
    return _opener.open(req, timeout=timeout)

def _public_peer(response):
    """The connected socket, not a second DNS lookup, decides whether a response is safe to read."""
    peer = getattr(response, "peer", None)                                 # deterministic test response
    if peer is None:
        fp = getattr(response, "fp", None)
        raw = getattr(fp, "raw", None)
        sock = getattr(raw, "_sock", None) or getattr(fp, "_sock", None)
        try:
            peer = sock.getpeername()[0]
        except (AttributeError, OSError, TypeError):
            return False
    try:
        return ipaddress.ip_address(str(peer).split("%", 1)[0]).is_global
    except ValueError:
        return False

def host(url):
    """The lower-case host of a URL without a leading www., or ''."""
    return (urllib.parse.urlsplit(url or "").hostname or "").lower().removeprefix("www.")

def public_url(url, resolve=True):
    """True only for an ordinary public HTTP(S) URL; fetches also verify every resolved address."""
    try:
        p = urllib.parse.urlsplit(url or "")
        if p.scheme not in ("http", "https") or not p.hostname or p.username is not None or p.password is not None:
            return False
        name = p.hostname.rstrip(".").lower()
        if name == "localhost" or name.endswith((".localhost", ".local", ".internal", ".home.arpa")):
            return False
        try:
            literal = ipaddress.ip_address(name.strip("[]"))
        except ValueError:
            literal = None
        if literal is not None:
            return literal.is_global
        if not resolve:
            return True
        answers = _resolve(name, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
        addresses = {ipaddress.ip_address(answer[4][0].split("%", 1)[0]) for answer in answers}
        return bool(addresses) and all(address.is_global for address in addresses)
    except (OSError, ValueError, UnicodeError):
        return False

def open_public(request, timeout):
    """Open at most five redirect hops, validating each destination before contact."""
    url, data, headers, method = request.full_url, request.data, dict(request.header_items()), request.get_method()
    for _ in range(6):
        if not public_url(url):
            raise UnsafeUrl("URL is not globally routable")
        current = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            response = _open(current, timeout)
        except urllib.error.HTTPError as error:
            if error.code not in (301, 302, 303, 307, 308) or not error.headers or not error.headers.get("Location"):
                raise
            url = urllib.parse.urljoin(url, error.headers["Location"])
            if error.code not in (307, 308):
                data, method = None, "GET"
            continue
        if not public_url(response.geturl(), resolve=False) or not _public_peer(response):
            response.close()
            raise UnsafeUrl("connected peer or final URL is not globally routable")
        return response
    raise UnsafeUrl("too many redirects")

def parse_xml(text):
    """Parse a capped untrusted XML response, refusing every DTD/entity declaration before ElementTree sees it."""
    if len(text.encode("utf-8")) > MAX_BYTES or re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
        raise ET.ParseError("DTD, entity declaration or oversized XML refused")
    return ET.fromstring(text)

def published(url):
    global _closed
    if _closed is None:
        _closed = set(json.loads(DISALLOWED.read_text())["urls"]) if DISALLOWED.exists() else set()
    return public_url(url, resolve=False) and host(url) not in TERMS_EXCLUDED and url not in _closed

def allowed(url):
    """Whether robots.txt lets AirStackBot fetch this URL. A missing robots.txt (4xx) allows everything; one that can't be read
    (5xx, no answer) means the host is treated as closed, as RFC 9309 says. A slow answer is still an answer: api.gdeltproject.org
    takes about 14 seconds to say 404, so the wait is 30 seconds."""
    if not public_url(url):
        return False
    p = urllib.parse.urlsplit(url); origin = f"{p.scheme}://{p.netloc}"
    with _lock:
        rp = _robots.get(origin)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            with open_public(urllib.request.Request(origin + "/robots.txt", headers={"User-Agent": UA}), ROBOTS_TIMEOUT) as r:
                rp.parse(r.read(500_000).decode("utf-8", "ignore").splitlines())
        except urllib.error.HTTPError as e:
            rp.allow_all, rp.disallow_all = 400 <= e.code < 500, e.code >= 500
        except Exception:
            rp.disallow_all = True
        with _lock:
            _robots[origin] = rp
    return rp.can_fetch(AGENT, url)

def text(url, timeout=25):
    """The body of a page that answered 200; anything else raises, for callers that cannot go on without it."""
    status, body, _ = get(url, timeout=timeout)
    if status != 200:
        raise RuntimeError(f"HTTP {status or 'no response'} for {url}")
    return body


def get(url, headers=None, timeout=25, robots=True, data=None):
    """GET, or POST when `data` (bytes) is given: a query API such as OSV's takes its question as a body."""
    if not public_url(url):
        return 0, "", {"x-url": "unsafe"}
    if host(url) in TERMS_EXCLUDED:
        return 0, "", {"x-terms": "excluded"}
    if robots and not allowed(url):
        return 0, "", {"x-robots": "disallowed"}
    h = {"User-Agent": UA, **(headers or {})}
    for attempt in (0, 1):
        try:
            with open_public(urllib.request.Request(url, data=data, headers=h), timeout) as r:
                return r.status, r.read(MAX_BYTES).decode("utf-8", "ignore"), {**{k.lower(): v for k, v in r.headers.items()}, "x-final-url": r.geturl()}
        except urllib.error.HTTPError as e:
            wait = e.headers.get("Retry-After", "") if e.headers else ""
            if attempt == 0 and e.code in (429, 503) and wait.isdigit() and int(wait) <= 60:
                time.sleep(int(wait)); continue
            return e.code, "", {}
        except Exception:
            return 0, "", {}
    return 0, "", {}

def sweep(urls, workers=16):
    """The pages robots.txt now closes to AirStackBot, out of `urls` (one robots.txt read per host)."""
    urls = sorted(set(urls))
    with ThreadPoolExecutor(workers) as ex:
        ok = list(ex.map(allowed, urls))
    return [u for u, a in zip(urls, ok) if not a]

if __name__ == "__main__" and "--sweep" in sys.argv:                       # every page behind a published fact or price
    import sqlite3
    from datetime import date
    c = sqlite3.connect(f"file:{paths.MARKET_DB}?mode=ro", uri=True)
    urls = {u for (u,) in c.execute("SELECT DISTINCT url FROM facts")} | {u for (u,) in c.execute("SELECT url FROM raw_items WHERE kind='pricing'")}
    urls |= {v["url"] for v in json.loads(paths.PRICING.read_text()).values()} if paths.PRICING.exists() else set()
    closed = sweep(u for u in urls if u.startswith("http"))
    DISALLOWED.write_text(json.dumps({"checked": date.today().isoformat(), "agent": AGENT, "of": len(urls), "urls": closed}, indent=0) + "\n")
    print(f"robots-disallowed.json: {len(closed)} of {len(urls)} pages closed to {AGENT}")
