# spec: AS-237
"""Check data/catalog.json against the live web, and write what was observed into each entry's "checked" field.
Every homepage and pricing URL is fetched (browser-like headers, redirects followed, 20 s timeout). An entry is kept only
if its homepage answers 2xx/3xx (or 403 from a bot wall) AND its page title or final host names the product or vendor.
A pricing URL that does not answer 2xx on a page of its own is set to null with the reason.
Each entry's "pages" (docs, integrations, security) are checked the same way: 2xx, on the vendor's own domain, a page of its
own (not the front page, a sign-in or a missing page) that names its kind; on a domain several products share, docs and
integrations must name the product. A failing page is set to null with the reason. An entry without "pages" has them found
from its homepage's own links first, then from the usual paths (/docs, help., /integrations, trust. ...) if they resolve.
Stdlib only; spends nothing.
  python tools/check_catalog.py [candidates.json]   check (default: data/catalog.json itself), rewrite data/catalog.json"""
import concurrent.futures, datetime, html, json, re, sys, time, urllib.error, urllib.parse, urllib.request, zlib
from pathlib import Path
from airstack import paths

ROOT = paths.ROOT
from airstack.catalog import CATEGORIES, PATH as CATALOG    # one list of categories for the checker and page
from airstack.fetch import UA, allowed                                   # one honest name; robots.txt obeyed (AS-274)
HEADERS = {"User-Agent": UA,
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip, deflate"}
BLOCKED = "blocked by the site's bot protection"
WALL = re.compile(r"just a moment|attention required|access denied|request has been blocked|robot or human|are you a robot|"
                  r"verify you are human|security check|pardon our interruption|captcha", re.I)
NOT_FOUND = re.compile(r"\b404\b|not found|doesn.t exist|no longer available", re.I)
PRICE_WORDS = re.compile(r"pric|plan|cost|fee|edition|tier|subscri|buy|upgrade", re.I)
STOP = {"com", "net", "org", "io", "ai", "app", "dev", "co", "www", "inc", "llc", "ltd", "the", "and", "for", "with",
        "labs", "software", "technologies", "corp"}
KINDS = ("docs", "integrations", "security")
KIND_WORDS = {"docs": re.compile(r"docs?\b|documentation|help|support|knowledge|guide|developer|manual|\bapi\b|reference", re.I),
              "integrations": re.compile(r"integrat|apps?[ -]?(directory|store|center|marketplace)|appexchange|extensions?\b|plugins?\b|add-?ons?\b|connectors?\b", re.I),
              "security": re.compile(r"security|trust|complian", re.I)}
URL_WORDS = {"docs": re.compile(r"(^|\.)learn\."), "integrations": re.compile(r"marketplace|ecosystem", re.I), "security": re.compile(r"$^")}
LOCALE = re.compile(r"[a-z]{2}[-_][a-z]{2}|en|de|fr|es|it|ja|ko|pt|nl|sv|da|fi|nb|pl|ru|tr|zh|intl", re.I)
ARTICLE = re.compile(r"\d{4,}|answers?|articles?|topics?|posts?|blog", re.I)
HOST_HINT = {"docs": ("docs", "help", "support", "developer", "developers", "learn", "knowledge", "kb"),
             "integrations": ("marketplace", "apps", "integrations", "ecosystem", "appcenter"), "security": ("trust", "security", "compliance")}
PATH_HINT = {"docs": r"docs?|documentation|help|help-?cent(er|re)|support|knowledge(-?base)?|kb|developers?|manual",
             "integrations": r"integrations?|marketplace|app-?(directory|marketplace|store|center|gallery)|extensions|plugins|add-?ons|connectors|ecosystem",
             "security": r"trust(-?cent(er|re))?|security|compliance"}
TEXT_HINT = {"docs": r"(help( cent(er|re))?|docs|documentation|support( cent(er|re))?|knowledge base|developers?|developer docs|api (docs|reference)|help & support|support & docs)",
             "integrations": r"(integrations?|marketplace|app (directory|marketplace|store|center|gallery)|apps & integrations|extensions|plugins|add-?ons|connectors)",
             "security": r"(trust( cent(er|re))?|security|compliance|security & trust|trust & security)"}
SKIP = re.compile(r"/(blog|news|press|careers?|jobs|contact\w*|events?|webinars?|podcasts?|customers?|case-stud|pricing|plans|demo|login|"
                  r"signin|sign-in|signup|sign-up|register|download|status|community|forum|privacy|terms|cookie|affiliate|become|bug-bounty)\b|"
                  r"\.(pdf|png|jpg|svg|zip)$", re.I)
MARKETING = re.compile(r"solutions?|products|use-cases?|industries|lp|cybersecurity", re.I)        # a sales page's first segment
SIGN_IN = re.compile(r"(^|[/.-])(log-?in|sign-?in|sign-?up|sso|auth|oauth|accounts?)([/.?]|$)", re.I)
NOT_SECURITY = re.compile(r"bug bounty|report (a )?(security issue|vulnerabilit)|\bstatus\b|cybersecurity|security solutions?", re.I)
FALLBACK = {"docs": ("https://help.{reg}/", "https://docs.{reg}/", "https://support.{reg}/", "https://{host}/docs", "https://{host}/help"),
            "integrations": ("https://{host}/integrations", "https://{host}/marketplace", "https://marketplace.{reg}/", "https://{host}/apps"),
            "security": ("https://trust.{reg}/", "https://{host}/trust", "https://{host}/security", "https://security.{reg}/")}
ORDER = ("id", "name", "category", "homepage", "pricing", "pages", "aliases", "vendor", "domain", "checked")

def get(url, limit):
    if not allowed(url):
        return None, url, "", b"", "robots.txt disallows AirStackBot"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=20) as r:
            return r.status, r.geturl(), r.headers.get("Content-Encoding", ""), r.read(limit), None
    except urllib.error.HTTPError as e:
        try:
            body = e.read(limit)
        except Exception:
            body = b""
        return e.code, e.geturl() or url, (e.headers or {}).get("Content-Encoding", ""), body, None
    except Exception as e:
        return None, url, "", b"", f"{type(e).__name__}: {e}"[:160]

def fetch(url, limit=600_000, retry=True):
    """GET url once (twice on a network error, 429 or 5xx unless retry is off); return the status, final URL, page <title>
    and the decoded body (callers drop it before anything is stored)."""
    status, final, enc, body, err = get(url, limit)
    if retry and (status is None or status == 429 or status >= 500):
        time.sleep(3)
        status, final, enc, body, err = get(url, limit)
    if "gzip" in enc or "deflate" in enc:
        try:
            body = zlib.decompressobj(47).decompress(body)                # 47: gzip or zlib header, truncation tolerated
        except zlib.error:
            pass
    m = re.search(rb"<title[^>]*>(.*?)</title>", body.split(b"</head>", 1)[0], re.S | re.I)    # not an <svg><title> in the body
    title = " ".join(html.unescape(m.group(1).decode("utf-8", "replace")).split())[:200] if m else None
    return {"status": status, "final_url": final, "title": title, **({"error": err} if err else {}), "body": body}

def tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(t) >= 3 and t not in STOP}

def squash(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def names(text, e):
    """True when text names the product or the vendor: every word of either label appears, or the label run together does."""
    words, squashed = tokens(text), squash(text)
    for label in (e["name"], e["vendor"]):
        need, run = tokens(label), squash(label)
        if (need and need <= words) or (len(run) >= 5 and run in squashed):
            return True
    return False

def is_front_page(url):
    parts = [p for p in urllib.parse.urlsplit(url).path.split("/") if p and not re.fullmatch(r"[a-z]{2}([-_][a-z]{2})?", p, re.I)]
    return not parts

def reg(host):
    """The registrable domain: the last two labels, three under a two-part suffix such as co.uk."""
    labels = (host or "").lower().rstrip(".").split(".")
    n = 3 if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in ("co", "com", "org", "net", "ac", "gov") else 2
    return ".".join(labels[-n:])

def host_of(url):
    return (urllib.parse.urlsplit(url).hostname or "").lower()

def owned(url, e, home_final):
    """True when url is on the vendor's own domain: the homepage's registrable domain, or one named for the product or vendor
    (zoom.us for Zoom, support.atlassian.com for Trello)."""
    r = reg(host_of(url))
    if r in (reg(host_of(e["homepage"])), reg(host_of(home_final))):
        return True
    label = r.split(".")[0]
    return len(label) >= 4 and label in {squash(e["name"]), squash(e["vendor"]), squash(e["vendor"].split()[0])}

def product_named(text, e):
    """True when text names this product rather than only its vendor (a product's own help, not the vendor-wide front)."""
    vendor, words = tokens(e["vendor"]), tokens(text)
    for i, label in enumerate([e["name"]] + e.get("aliases", [])):
        need = tokens(label) - vendor or (tokens(label) if i == 0 else set())     # an alias that is only the vendor's name says nothing
        if need and need <= words or len(squash(label)) >= 5 and squash(label) != squash(e["vendor"]) and squash(label) in squash(text):
            return True
    return False

def judge(kind, url, e, home, shared, how):
    """Fetch one candidate page; return what was observed and why it is not this product's page (None when it is)."""
    pg = fetch(url, limit=300_000, retry=False)
    pg.pop("body")
    rec = {"tried": url, "status": pg["status"], "final_url": pg["final_url"], "title": pg["title"]}
    final, title = pg["final_url"], pg["title"] or ""
    s = urllib.parse.urlsplit(final)
    if pg["status"] is None:
        return rec, f"unreachable ({pg.get('error')})"
    if not 200 <= pg["status"] < 300:
        return rec, f"returned {pg['status']}" + (" (bot protection), so it could not be confirmed" if pg["status"] == 403 else "")
    if not (owned(url, e, home["final_url"]) and owned(final, e, home["final_url"])):
        return rec, f"not on the vendor's own domain ({s.hostname})"
    if WALL.search(title):
        return rec, f"answered with a bot-protection page ({title!r}), so it could not be confirmed"
    if final.split("?")[0].rstrip("/") == home["final_url"].split("?")[0].rstrip("/") or \
            (is_front_page(final) and (s.hostname or "").removeprefix("www.") in (reg(s.hostname), host_of(home["final_url"]).removeprefix("www."))):
        return rec, "lands on the site's front page"
    if SIGN_IN.search(f"{s.hostname}{s.path}") or re.match(r"\s*(sign|log) ?in\b", title, re.I):
        return rec, f"lands on a sign-in page ({final})"
    if NOT_FOUND.search(title):
        return rec, f"title says it is missing: {title!r}"
    if not (KIND_WORDS[kind].search(f"{s.hostname}{s.path} {title}") or URL_WORDS[kind].search(f"{s.hostname}{s.path}")):
        return rec, f"the page it lands on does not name {kind} ({final}, {title!r})"
    if how == "usual path" and not KIND_WORDS[kind].search(title):              # a guessed path can be an app shell answering 200
        return rec, f"a guessed path whose title does not name {kind} ({title!r}), so it could not be confirmed"
    if how == "usual path" and host_of(url).removeprefix("www.") != host_of(home["final_url"]).removeprefix("www.") and not names(title, e):
        return rec, f"a guessed subdomain whose title does not name {e['name']} ({title!r}), so it may be a customer's site"
    if kind == "integrations" and re.search(r"\bdownload", title, re.I) and not re.search(r"marketplace|integrat|app (directory|store)", title, re.I):
        return rec, f"a download page, not integrations ({title!r})"
    first = ([p for p in s.path.split("/") if p and not LOCALE.fullmatch(p)] or [""])[0]
    if kind == "security" and ((NOT_SECURITY.search(title) and not re.search(r"\btrust\b", title, re.I)) or MARKETING.fullmatch(first)):
        return rec, f"a vulnerability-report, status or sales page, not the vendor's security overview ({final}, {title!r})"
    if kind == "security" and e["category"] == "security-it" and not re.search(r"trust|complian", f"{s.hostname}{s.path} {title}", re.I):
        return rec, f"a security vendor's page that names neither trust nor compliance, so it may be a product page ({final})"
    if title == (home["title"] or "") and not KIND_WORDS[kind].search(title):
        return rec, "it has the homepage's own title, so it could not be confirmed to be a page of its own"
    if shared and kind != "security" and not product_named(f"{s.hostname} {s.path} {title}", e):
        return rec, f"a vendor-wide page that does not name {e['name']} ({final}, {title!r})"
    return rec, None

def links(body, home_final):
    """Every <a href> on the homepage: (absolute URL without query or fragment, its visible text)."""
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    for m in re.finditer(r"<a\b[^>]*?\bhref\s*=\s*[\"']([^\"'#>]+)[^>]*>(.*?)</a>", text, re.S | re.I):
        u = urllib.parse.urljoin(home_final, html.unescape(m.group(1)).strip())
        if u.startswith(("https://", "http://")):
            u = "https://" + u.split("://", 1)[1]                          # ask for the secure page; the check sees where it lands
            yield urllib.parse.urlunsplit(urllib.parse.urlsplit(u)._replace(query="", fragment="")), \
                  " ".join(html.unescape(re.sub(r"<[^>]+>", " ", m.group(2))).split())[:80].lower()

def discover(kind, body, e, home):
    """Candidate URLs for one kind of page, best first: the homepage's own links, then the usual paths."""
    scored = {}
    for u, text in links(body, home["final_url"]):
        s = urllib.parse.urlsplit(u)
        host = (s.hostname or "").lower()
        if not owned(u, e, home["final_url"]) or SKIP.search(s.path) or SIGN_IN.search(f"{host}{s.path}"):
            continue
        parts = [p for p in s.path.lower().split("/") if p and not LOCALE.fullmatch(p)]
        if len(parts) > 3 or any(ARTICLE.search(p) for p in parts) or (kind != "integrations" and parts and
                                                                         (MARKETING.fullmatch(parts[0]) or kind == "docs" and parts[0] in ("features", "product"))):
            continue                                                       # one article or post, or a sales page, not the section's front
        sub = host.removesuffix(reg(host)).removeprefix("www.").split(".")[0]
        score = 4 * (sub in HOST_HINT[kind]) + 3 * bool(parts and re.fullmatch(PATH_HINT[kind], parts[0])) \
            + 3 * bool(re.fullmatch(TEXT_HINT[kind], text)) + 2 * bool(any(re.fullmatch(PATH_HINT[kind], p) for p in parts[1:])) \
            - 2 * max(0, len(parts) - 1)
        score += 2 * (kind == "docs" and bool(re.search(r"help|support|knowledge|kb", f"{sub} {' '.join(parts[:1])} {text}")))  # a help centre before API docs
        if score >= 3:
            scored[u] = max(score, scored.get(u, 0))
    fronts = [u for u in scored if not any(v != u and u.startswith(v.rstrip("/") + "/") for v in scored)]   # a section's front, not a page in it
    top = sorted(fronts, key=lambda u: (-scored[u], len(u)))[:3]
    host = host_of(home["final_url"]) or host_of(e["homepage"])
    guessed = [p.format(reg=reg(host), host=host) for p in FALLBACK[kind]]
    return [(u, "homepage link") for u in top] + [(u, "usual path") for u in guessed if u not in top]

def check_pages(e, prior, body, home):
    """Fill e["pages"] and the observations in checked["pages"]: verify the given URLs, or find them when none were given."""
    given, before, out = e.get("pages"), (prior.get("pages") or {}), {}
    shared = sum(reg(d) in (reg(e["domain"]), reg(host_of(home["final_url"]))) or v == e["vendor"] for d, v in OTHERS) > 1   # a vendor of several products
    for kind in KINDS:
        if given is not None and kind in given:
            tried = given[kind] or (before.get(kind) or {}).get("tried")
            cands = [(tried, (before.get(kind) or {}).get("found", "given"))] if tried else []
            if not cands:
                out[kind] = {"null_reason": (before.get(kind) or {}).get("null_reason") or f"no {kind} URL was given to check"}
        else:
            cands = discover(kind, body, e, home)                         # an unread homepage still gets the usual paths
        first = None
        for url, how in cands:
            rec, why = judge(kind, url, e, home, shared, how)
            if why is None:
                out[kind] = {**rec, "found": how}
                break
            first = first or ({**rec, "found": how}, why)                   # the best-ranked candidate's failure is the one reported
        else:
            if cands:
                links_tried = sum(h == "homepage link" for _, h in cands)
                note = "" if len(cands) == 1 else f" ({links_tried} homepage links and {len(cands) - links_tried} usual paths tried, none confirmed)"
                if first[0]["found"] == "usual path" and not links_tried:
                    note = f" (no link on the homepage names it; {len(cands)} usual paths tried, none confirmed)"
                out[kind] = {**first[0], "null_reason": f"{first[0]['tried']}: {first[1]}{note}"}
    e["pages"] = {k: out[k]["tried"] if "null_reason" not in out[k] else None for k in KINDS}
    return out

def check(e, today):
    """Return the entry with "checked" filled in, and why it is dropped (None when kept)."""
    prior = e.get("checked") or {}
    home = fetch(e["homepage"], limit=4_000_000)
    body = home.pop("body")
    status = home["status"]
    host = urllib.parse.urlsplit(home["final_url"]).hostname or ""
    ck = {"date": today, "status": status, "final_url": home["final_url"], "title": home["title"]}
    if status == 403 or (status and status < 400 and WALL.search(home["title"] or "") and not names(home["title"], e)):
        ck["reachable"] = BLOCKED
    else:
        ck["reachable"] = "yes" if status and status < 400 else "no"
    ck["title_matches"], ck["host_matches"] = names(home["title"], e), names(host, e)
    if "error" in home:
        ck["error"] = home["error"]
    why = None
    if e["category"] not in CATEGORIES:
        why = f"unknown category {e['category']!r}"
    elif ck["reachable"] == "no":
        why = f"homepage returned {status}" if status else f"homepage unreachable twice ({home.get('error')})"
    elif not (ck["title_matches"] or ck["host_matches"]):
        why = f"neither the title {home['title']!r} nor the host {host} names {e['name']} or {e['vendor']}"
    tried = e.get("pricing") or prior.get("pricing_tried")
    reason = None
    if not tried:
        reason = prior.get("pricing_null_reason") or "no pricing URL was given to check"
    else:
        pr = fetch(tried)
        ck.update(pricing_tried=tried, pricing_status=pr["status"], pricing_final_url=pr["final_url"], pricing_title=pr["title"])
        if pr["status"] is None:
            reason = f"pricing page unreachable ({pr.get('error')})"
        elif not 200 <= pr["status"] < 300:
            reason = f"pricing page returned {pr['status']}" + (" (bot protection), so it could not be confirmed" if pr["status"] == 403 else "")
        elif WALL.search(pr["title"] or ""):
            reason = f"pricing page answered with a bot-protection page ({pr['title']!r}), so it could not be confirmed"
        elif is_front_page(pr["final_url"]):
            reason = "pricing URL lands on the site's front page"
        elif NOT_FOUND.search(pr["title"] or ""):
            reason = f"pricing page title says it is missing: {pr['title']!r}"
        elif not PRICE_WORDS.search(f"{pr['final_url']} {pr['title']}"):
            reason = f"the page it lands on does not name pricing or plans ({pr['final_url']}, {pr['title']!r})"
    e["pricing"] = None if reason else tried
    if reason:
        ck["pricing_null_reason"] = reason
    if why is None:
        ck["pages"] = check_pages(e, prior, body if 200 <= (status or 0) < 300 else b"", home)
    e["checked"] = ck
    return {k: e[k] for k in ORDER if k in e} | {k: v for k, v in e.items() if k not in ORDER}, why

OTHERS = []                                                               # every entry's (domain, vendor): who shares a vendor or a domain

def main(argv):
    src = Path(argv[1]) if len(argv) > 1 else CATALOG
    entries = json.loads(src.read_text())
    OTHERS[:] = [(e["domain"], e["vendor"]) for e in entries]
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        results = list(pool.map(lambda e: check(e, today), entries))
    kept = [e for e, why in results if why is None]
    CATALOG.write_text(json.dumps(kept, indent=1, ensure_ascii=False) + "\n")
    cats = {}
    for e in kept:
        cats[e["category"]] = cats.get(e["category"], 0) + 1
    print(f"kept {len(kept)} of {len(entries)} · pricing confirmed {sum(e['pricing'] is not None for e in kept)} · "
          + " · ".join(f"{k} confirmed {sum(e['pages'][k] is not None for e in kept)}" for k in KINDS) + f" · checked {today}")
    print("per category: " + ", ".join(f"{k} {v}" for k, v in cats.items()))
    for e, why in results:
        if why:
            print(f"DROPPED {e['id']}: {why}")
    for e in kept:
        if not e["checked"]["title_matches"]:
            print(f"TITLE   {e['id']}: {e['checked']['reachable']}, status {e['checked']['status']}, title {e['checked']['title']!r}")
    for e in kept:
        if e["pricing"] is None:
            print(f"PRICING {e['id']}: null, {e['checked']['pricing_null_reason']}")
    for e in kept:
        for k in KINDS:
            if e["pages"][k] is None:
                print(f"PAGE    {e['id']} {k}: null, {e['checked']['pages'][k]['null_reason']}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
