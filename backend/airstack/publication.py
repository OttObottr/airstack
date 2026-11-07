# spec: AS-223 AS-232
"""The publication hold: what may reach a public page or published snapshot.

The stored records are never altered: they are the audit trail. Only the public projection is cleaned. A third-party review or blog is
COMMENTARY: it may be fetched and stored, but it never appears as a citation, a source, or the words of a reason. Consequential
allegations (lawsuits, biometric or privacy claims) belong to a court, regulator or vendor record, and none is held here.

A new verdict may rest only on a CITABLE source (AS-232): the vendor's own site, the platform maker's documentation, a store listing,
a package registry or code host, or a regulator's or court's record. Anything else (a review, a blog, the press, a domain not tied to
anyone) may be read, never cited: a judge that cites it is held and the verdict is not published."""
import functools, gzip, json, re, sqlite3
from pathlib import Path
from urllib.parse import urlparse
from . import paths

COMMENTARY_HOSTS = {"javisreview.com"}                       # opinion sites seen in search results; add a host here to withhold it everywhere
ALLEGATION = re.compile(r"biometric|voiceprint|lawsuit|alleg|\breview\b[^.]{0,40}\bflags?\b", re.I)
REASON_KEYS = {"reason", "stored_reason", "rationale", "why", "message", "basis", "still_lapsed"}   # prose that speaks in AirStack's own voice

def _bad_url(v):
    return isinstance(v, str) and v.startswith("http") and (urlparse(v).hostname or "").removeprefix("www.") in COMMENTARY_HOSTS

def drop_allegations(text):
    return " ".join(s for s in re.split(r"(?<=[.!?])\s+", text) if not ALLEGATION.search(s)).strip()

def _refs(o, out):
    if isinstance(o, dict):
        if "ref" in o and any(_bad_url(v) for v in o.values()):
            out.add(o["ref"])
        for v in o.values(): _refs(v, out)
    elif isinstance(o, list):
        for v in o: _refs(v, out)

_DROP = object()                                              # "remove this item" (None is a real value in the data)

def _clean(o, refs, key=None):
    if isinstance(o, dict):
        if any(_bad_url(v) for v in o.values()):
            return _DROP                                      # an item (evidence row, search result, source) that points at commentary
        out = {}
        for k, v in o.items():
            c = _clean(v, refs, k)
            if c is not _DROP: out[k] = c
        return out
    if isinstance(o, list):
        items = []
        for v in o:
            if _bad_url(v) or (key == "citations" and v in refs): continue
            c = _clean(v, refs, key)
            if c is not _DROP: items.append(c)
        return items
    if isinstance(o, str) and key in REASON_KEYS:
        if ALLEGATION.search(o): o = drop_allegations(o)
        o = re.sub("|".join(map(re.escape, COMMENTARY_HOSTS)), "a third-party review", o)   # a held outcome names the host it held; the page does not
        return re.sub(r"\bseat(s?)\b", lambda m: "team" + m.group(1), o)         # vocabulary: our prose says team and plan, never seat
    return o

def hold(data):
    """A copy of `data` with commentary sources and allegation sentences removed. Idempotent."""
    refs = set(); _refs(data, refs)
    return _clean(data, refs)

def held_text(s):
    """True if a serialized public file still carries what the hold removes (used by the release test)."""
    return any(h in s for h in COMMENTARY_HOSTS) or bool(re.search(r"biometric consent|Voiceprint", s))

# ---- AS-232: what a new verdict may cite ----
# Makers are exact hosts and a vendor is its homepage's own host (and its subdomains), never a whole platform: github.io, org.uk, google.com.
STORES = {"chromewebstore.google.com", "apps.apple.com", "play.google.com"}                      # listings the vendor controls (as in build_chain_data)
MAKERS = {"support.google.com", "workspace.google.com", "workspaceupdates.googleblog.com", "blog.google",      # Meet
          "zoom.com", "zoom.us", "support.zoom.com", "learn.microsoft.com", "support.microsoft.com"}           # Zoom, Teams
REGISTRIES = {"registry.npmjs.org", "api.npmjs.org", "npmjs.com", "pypi.org", "github.com", "api.github.com"}   # not pypistats.org or web.archive.org: copies made by third parties
PUBLIC_RECORDS = (".gov", ".gov.uk", ".europa.eu")                                               # regulators and courts
SHARED = {"github.com", "huggingface.co", "gitlab.com"}                                          # one host, many owners: the first path segment is the owner
USER_CONTENT = re.compile(r"^(?:community|communities|answers|techcommunity|forums?|discuss|discussions|groups|sites)\.|/(?:answers|threads?|community|forums?|discussions?)(?:/|$)")
DATA = paths.DATA

def _host(u):
    return (urlparse(u).hostname or "").removeprefix("www.") if isinstance(u, str) else ""

def _site(u):
    """What one owner publishes under: the host, or host/owner on a shared host (huggingface.co/docs, github.com/openai)."""
    h, seg = _host(u), urlparse(u).path.strip("/").split("/")[0]
    return f"{h}/{seg}" if h in SHARED and seg else h

@functools.cache
def own_domains():
    """Tool id -> the site of its own homepage, from the tracked universe and the catalog. No file: no vendor is known."""
    out = {}
    for path in (paths.UNIVERSE, paths.CATALOG):
        for e in json.loads(path.read_text()) if path.exists() else []:
            if e.get("homepage"): out.setdefault(e["id"], _site(e["homepage"]))
    return out

def source_class(url, own=()):
    """The citable class of a source, or None. `own`: the vendor's own sites. User content (forums, community threads, personal sites)
    is never citable, even on a maker's own domain, and unknown is never citable."""
    if not isinstance(url, str): return None
    h, s = _host(url), _site(url)
    if USER_CONTENT.search(h + urlparse(url).path): return None
    if h in STORES: return "store"
    if any(s == d or s.endswith("." + d) for d in own): return "vendor"
    if h in MAKERS: return "maker"
    if h in REGISTRIES: return "registry"
    if ("." + h).endswith(PUBLIC_RECORDS): return "regulator or court"
    return None

def uncitable(citations, evidence, tool):
    """The cited evidence rows a verdict on `tool` may not rest on, as "f10 (javisreview.com)". Empty when every citation is citable.
    A row is the vendor's own when it is on the homepage site of `tool` or of the entity the fact is about (its key's first part)."""
    rows, own = {e["ref"]: e for e in evidence}, own_domains()
    out = []
    for ref in citations:
        e = rows.get(ref)
        if e is not None and source_class(e.get("url"), {own.get(tool), own.get(e.get("key", "").split(".")[0])} - {None}) is None:
            out.append(f"{ref} ({_host(e.get('url')) or 'no source'})")
    return out


# ---- public facts and list prices: current evidence only ---------------------------------------------------------

def latest_rechecks(conn=None, log_dir=None, successful_only=False):
    """Latest re-check per URL from the private database and the append-only daily logs.

    A failed fetch is useful in the evidence receipt, but it never supersedes the last check that actually read or conditionally
    verified a page. Set ``successful_only`` for a publication decision.
    """
    latest = {}
    def keep(row, order):
        if not isinstance(row, dict) or not row.get("url"):
            return
        if successful_only and row.get("outcome") == "fetch_failed":
            return
        key = (row.get("checked_at") or "", order)
        if key >= latest.get(row.get("url"), (("", ""), None))[0]:
            latest[row.get("url")] = (key, row)
    close = False
    if conn is None and paths.MARKET_DB.exists():
        conn = sqlite3.connect(f"file:{paths.MARKET_DB}?mode=ro", uri=True)
        close = True
    if conn is not None:
        try:
            for row in conn.execute("SELECT id,url,checked_at,outcome,note,quotes_ok,quotes_total FROM rechecks ORDER BY checked_at,id"):
                keep(dict(zip(("id", "url", "checked_at", "outcome", "note", "quotes_ok", "quotes_total"), row)), f"db:{row[0]:012d}")
        except sqlite3.DatabaseError:                                  # a small fixture or an older private database without rechecks
            pass
        finally:
            if close:
                conn.close()
    root = paths.DATA / "rechecks" if log_dir is None else Path(log_dir)
    for file in sorted(root.glob("*.jsonl.gz")) if root.exists() else []:
        try:
            lines = gzip.decompress(file.read_bytes()).decode().splitlines()
        except (OSError, UnicodeError):
            continue                                                    # a partial log is not evidence of either success or failure
        for number, line in enumerate(lines):
            try:
                keep(json.loads(line), f"log:{file.name}:{number:012d}")
            except (TypeError, ValueError):
                continue
    return {url: row for url, (_, row) in latest.items() if url}


def missing_quote_urls(conn=None, log_dir=None):
    """Pages whose latest successful live check says one or more published quotes disappeared."""
    return {url for url, row in latest_rechecks(conn, log_dir, successful_only=True).items()
            if row.get("outcome") == "changed_quotes_missing"}


def _json(path, fallback):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return fallback


def _url_key(url):
    p = urlparse(url or "")
    try:
        port = p.port
    except ValueError:
        return ()
    return (p.scheme.lower(), (p.hostname or "").lower().removeprefix("www."), port, p.path.rstrip("/") or "/", p.query)


def _registered(host):
    """A dependency-free site boundary, including the common two-part public suffixes in the catalog."""
    labels = (host or "").lower().rstrip(".").split(".")
    three = len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in {"co", "com", "org", "net", "ac", "gov"}
    return ".".join(labels[-(3 if three else 2):])


def price_page_owned(homepage, price_url, shared_hosts=()):
    """Whether a price page can be attributed to this product without guessing across owners or shared hosts."""
    home, price = urlparse(homepage or ""), urlparse(price_url or "")
    hh, ph = (home.hostname or "").lower().removeprefix("www."), (price.hostname or "").lower().removeprefix("www.")
    if not hh or not ph:
        return False
    shared = set(shared_hosts)
    if hh in shared or ph in shared:
        # github.com/org/repo does not own github.com/pricing. The platform's own root may own its pricing page.
        return hh == ph and (home.path.rstrip("/") in ("", "/"))
    return _registered(hh) == _registered(ph)


def price_context(catalog=None, universe=None, directory=None):
    """Curated exact price pages and homepages used to attribute a public price to one product."""
    catalog = _json(paths.CATALOG, []) if catalog is None else catalog
    universe = _json(paths.UNIVERSE, []) if universe is None else universe
    directory = _json(paths.DIRECTORY, {"products": []}) if directory is None else directory
    homes, exact = {}, {}
    for entry in [*catalog, *universe]:
        pid = entry.get("id")
        if pid and entry.get("homepage"):
            homes[pid] = entry["homepage"]
        price = entry.get("pricing") or (entry.get("pages") or {}).get("pricing")
        if pid and price:
            exact[pid] = price
    for row in directory.get("products", []):
        if len(row) > 3 and row[3]:
            homes.setdefault(row[0], row[3])
    return homes, exact


def owned_prices(prices, homes, exact=(), missing=(), shared_hosts=(), can_publish=None):
    """The conservative public projection of extracted prices. Stored/model records remain untouched."""
    exact, missing = dict(exact), set(missing)
    if can_publish is None:
        from .fetch import published as can_publish
    out = {}
    for pid, row in (prices or {}).items():
        if not isinstance(row, dict) or not row.get("url") or not row.get("plans") or row["url"] in missing or not can_publish(row["url"]):
            continue
        if pid in exact:
            ok = _url_key(row["url"]) == _url_key(exact[pid])
        else:
            ok = price_page_owned(homes.get(pid), row["url"], shared_hosts)
        if ok:
            out[pid] = row
    return out


def public_prices(prices, conn=None, missing=None, catalog=None, universe=None, directory=None):
    """Prices safe for every public surface: attributable to the product, publishable, and still backed by their quotes."""
    homes, exact = price_context(catalog, universe, directory)
    policy = paths.config("pricing")
    missing = missing_quote_urls(conn) if missing is None else missing
    return owned_prices(prices, homes, exact, missing, policy.get("shared_hosts", ()))
