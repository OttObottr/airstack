# spec: AS-265 AS-295
"""What changed, in each vendor's own words: the daily feed of dated announcements from the products AirStack tracks.

Three free sources, no key, no model:
- changelogs and blogs: the RSS or Atom feed each catalog product's own homepage links to (or a common feed path on its own
  site); an item counts only if it links to the vendor's own domain.
- releases: GitHub's releases API for every tracked tool with a repository (via the gh CLI's own login).
- Hacker News: stories whose link is the product's own site (Algolia's public HN API), with their points and discussion link.
Every raw response is saved per day (data/news-raw/), and news.json is rebuilt offline from them.
Feeds are untrusted input: a document with a DTD or an entity declaration is refused, and every body is capped at 2 MB.

Usage: ../.venv/bin/python tools/build_news.py --fetch    # read today's feeds, releases and stories, then build
       ../.venv/bin/python tools/build_news.py            # rebuild news.json from the saved responses"""
import argparse, gzip, json, re, subprocess, time, urllib.parse, urllib.request
from xml.etree.ElementTree import ParseError
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from airstack import paths
from airstack.fetch import host, parse_xml

ROOT = paths.ROOT
RAW, OUT = paths.DATA / "news-raw", paths.NEWS
MAX_BYTES, DAYS = 2_000_000, 30
FEED_LINK = re.compile(r"<link\b[^>]*\btype=[\"']application/(?:rss|atom)\+xml[\"'][^>]*>", re.I)
HREF = re.compile(r"\bhref=[\"']([^\"']+)[\"']", re.I)
CHANGELOG = re.compile(r"changelog|release-?notes|/releases|whats-?new|product-?updates|/updates", re.I)
PRERELEASE = re.compile(r"^b\d+$|nightly|canary|alpha|beta|\brc\d*\b|preview|snapshot|dev\d", re.I)
VERSION_ONLY = re.compile(
    r"^(?!.*\b(?:add(?:ed|s)?|fix(?:ed|es)?|improv(?:e|ed|es)|introduc(?:e|ed|es)|remov(?:e|ed|es)|support(?:ed|s)?|deprecat(?:e|ed|es)|secur(?:e|ity)|migrat(?:e|ed|ion)|upgrad(?:e|ed|es))\b)"
    r"(?:(?:version|release)\s+|[A-Za-z0-9@_./:-]+(?:\s+[A-Za-z0-9@_./:-]+){0,6}?(?:==|@|:\s*|\s+|-))?v?\d+(?:\.\d+){1,4}(?:[-+][\w.-]+)?$", re.I)
COMPANY_SUBDOMAINS = {"blog", "docs", "engineering", "status", "news", "about", "help", "support", "developers", "developer", "dev", "changelog", "community"}
PER_KIND = 3                                                               # the latest three of each kind per product: one busy repo can't fill the feed
GUESSES = ("/changelog/rss.xml", "/changelog.rss", "/changelog/feed.xml", "/blog/rss.xml", "/blog/feed", "/feed", "/rss.xml", "/feed.xml", "/atom.xml")

def get(url, accept="*/*"):
    from airstack.fetch import get as _get   # one honest name; robots.txt obeyed (AS-274)
    status, body, h = _get(url, {"Accept": accept, "Accept-Language": "en-US,en"}, timeout=15)
    return status, body[:MAX_BYTES], h.get("x-final-url", url)

def own(link, domain):
    h = host(link); d = domain.lower().removeprefix("www.")
    return h == d or h.endswith("." + d)

def when(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")

def parse_feed(body):
    """[(title, link, date)] from RSS 2.0 or Atom. Refuses DTDs and entities (an untrusted document can't expand itself)."""
    try:
        root = parse_xml(body)
    except ParseError:
        return []
    tag = lambda e: e.tag.rsplit("}", 1)[-1]
    out = []
    for e in root.iter():
        if tag(e) not in ("item", "entry"):
            continue
        f = {tag(c): c for c in e}
        title = (f["title"].text or "").strip() if "title" in f else ""
        link = (f["link"].text or f["link"].get("href") or "").strip() if "link" in f else ""
        if "link" in f and tag(e) == "entry":
            alt = [c.get("href") for c in e if tag(c) == "link" and c.get("rel", "alternate") == "alternate" and c.get("href")]
            link = alt[0] if alt else link
        date = next((when(f[k].text) for k in ("pubDate", "published", "updated", "date") if k in f and f[k].text), None)
        if title and link and date:
            out.append((re.sub(r"\s+", " ", title)[:200], link, date))
    return out

def release_summary(body):
    """First substantive publisher-written line from GitHub release notes; never generate or infer one."""
    text = re.sub(r"```.*?```", " ", body or "", flags=re.S)
    text = re.sub(r"!?(?:\[([^]]*)\])\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    skip = re.compile(r"^(?:what'?s changed|changes?|changelog|release notes?|full changelog|contributors?|checksums?|assets?)\s*:?$", re.I)
    for raw in text.splitlines():
        line = re.sub(r"^\s*(?:#{1,6}|[-*+]\s+|>\s*)", "", raw).strip()
        line = re.sub(r"\s+", " ", line)
        line = re.sub(r"\s+by\s+@[\w-]+(?:\s+in\s+https?://\S+)?\s*$", "", line, flags=re.I)
        if skip.fullmatch(line) or VERSION_ONLY.fullmatch(line) or line.lower().startswith("compare: http"):
            continue
        if len(line) >= 18 and len(re.findall(r"[A-Za-z]{2,}", line)) >= 3:
            return line[:240]
    return None

def discover(p):
    """The feeds a product's own homepage links to, else the first common feed path on its own site that parses."""
    status, body, final = get(p["homepage"], "text/html")
    feeds = []
    if status == 200:
        for tag_ in FEED_LINK.findall(body[:300000]):
            m = HREF.search(tag_)
            if m:
                u = urllib.parse.urljoin(final, m.group(1))
                if own(u, p["domain"]) and u not in feeds:
                    feeds.append(u)
    if not feeds:
        origin = f"{urllib.parse.urlsplit(final if status == 200 else p['homepage']).scheme}://{urllib.parse.urlsplit(final if status == 200 else p['homepage']).netloc}"
        for g in GUESSES:
            s, b, _ = get(origin + g, "application/rss+xml, application/atom+xml, application/xml")
            if s == 200 and parse_feed(b):
                feeds.append(origin + g); break
    return feeds[:3]

BATCH = {}
def save(day, name, body):                                                 # one file a day (data/news-raw/<day>.json.gz), written at the end of the fetch
    BATCH[name] = body

def flush(day):
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{day}.json.gz").write_bytes(gzip.compress(json.dumps(BATCH, ensure_ascii=False, sort_keys=True).encode(), mtime=0))

def fetch():
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d"); now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    catalog = json.loads(paths.CATALOG.read_text())
    known = RAW / "feeds.json"; feeds = json.loads(known.read_text()) if known.exists() else {}
    todo = [p for p in catalog if p["id"] not in feeds and p.get("homepage")]
    with ThreadPoolExecutor(16) as ex:
        for p, f in zip(todo, ex.map(discover, todo)):
            feeds[p["id"]] = f
    known.parent.mkdir(parents=True, exist_ok=True); known.write_text(json.dumps(feeds, indent=0, sort_keys=True))
    def read(p):
        items = []
        for u in feeds.get(p["id"], []):
            s, b, _ = get(u, "application/rss+xml, application/atom+xml, application/xml")
            items += [{"title": t, "url": l, "date": d, "feed": u} for t, l, d in parse_feed(b) if own(l, p["domain"])]
        return p, items
    with ThreadPoolExecutor(16) as ex:
        for p, items in ex.map(read, [p for p in catalog if feeds.get(p["id"])]):
            save(day, f"feed--{p['id']}", {"fetched_at": now, "id": p["id"], "feeds": feeds[p["id"]], "items": items})
    for t in json.loads(paths.UNIVERSE.read_text()):
        if t.get("github") and re.fullmatch(r"[\w.-]+/[\w.-]+", t["github"]):
            out = subprocess.run(["gh", "api", f"repos/{t['github']}/releases?per_page=5"], capture_output=True, text=True)
            rel = json.loads(out.stdout) if out.returncode == 0 else []
            save(day, f"release--{t['id']}", {"fetched_at": now, "id": t["id"], "repo": t["github"], "items": [
                {"title": r.get("name") or r.get("tag_name"), "body": (r.get("body") or "")[:20_000], "url": r["html_url"], "date": r.get("published_at")} for r in rel if not r.get("draft") and r.get("published_at")]})
    since = int((datetime.now(timezone.utc) - timedelta(days=DAYS)).timestamp())
    for p in catalog:
        q = urllib.parse.urlencode({"query": p["domain"], "tags": "story", "restrictSearchableAttributes": "url", "numericFilters": f"created_at_i>{since}", "hitsPerPage": 20})
        s, b, _ = get(f"https://hn.algolia.com/api/v1/search_by_date?{q}", "application/json")
        hits = json.loads(b).get("hits", []) if s == 200 else []
        save(day, f"hn--{p['id']}", {"fetched_at": now, "id": p["id"], "query": q, "items": [
            {"title": h["title"], "url": h["url"], "date": h["created_at"], "points": h.get("points"), "discussion": f"https://news.ycombinator.com/item?id={h['objectID']}"}
            for h in hits if h.get("url") and own(h["url"], p["domain"])]})
        time.sleep(0.3)
    flush(day)

def build():
    days = sorted(f.name[:10] for f in RAW.glob("????-??-??.json.gz")) if RAW.exists() else []
    if not days:
        print("news.json: nothing fetched yet"); return
    day = json.loads(gzip.decompress((RAW / f"{days[-1]}.json.gz").read_bytes()))
    catalog = json.loads(paths.CATALOG.read_text())
    names = {p["id"]: p["name"] for p in catalog} | {t["id"]: t["name"] for t in json.loads(paths.UNIVERSE.read_text())}
    shared, domain = {}, {p["id"]: p["domain"].lower().removeprefix("www.") for p in catalog}
    for p in catalog:
        shared[p["domain"]] = shared.get(p["domain"], 0) + 1
    addr = lambda u: (host(u) + urllib.parse.urlsplit(u).path).rstrip("/").lower()
    home = {p["id"]: addr(p["homepage"]) for p in catalog if shared[p["domain"]] > 1 or urllib.parse.urlsplit(p["homepage"]).path.strip("/")}
    # a product on a shared host (github.com/features/copilot) owns only its own path there, not every link to the host
    cutoff = (datetime.fromisoformat(min(v["fetched_at"] for v in day.values())) - timedelta(days=DAYS)).isoformat()
    items, seen = [], set()
    for name, d in sorted(day.items()):
        kind = name.split("--")[0]
        count = {}
        for it in sorted(d["items"], key=lambda i: when(i["date"]) or "", reverse=True):
            k = "release" if kind == "release" else "hn" if kind == "hn" else "changelog" if CHANGELOG.search(it["url"] + " " + d.get("feeds", [""])[0]) else "blog"
            if kind == "release" and PRERELEASE.search(it["title"] or ""):
                continue
            summary = release_summary(it.get("body")) if kind == "release" else None
            if kind == "release" and VERSION_ONLY.fullmatch((it["title"] or "").strip()) and not summary:
                continue                                                   # a version is evidence of a release, not an explanation of what changed
            title = summary or it["title"]
            if re.search(r"\$\s?\d", title or ""):
                continue                                                   # no dollar amounts on screen: a headline carrying one is left out, not rewritten
            dm = domain.get(d["id"], "")
            sub = host(it["url"])[: -len(dm) - 1] if kind == "hn" and host(it["url"]).endswith("." + dm) else ""
            if kind == "hn" and sub and sub not in COMPANY_SUBDOMAINS:
                continue                                                   # alice.wordpress.com is a user's site, not WordPress.com's news
            if kind == "hn" and d["id"] in home and (not addr(it["url"]).startswith(home[d["id"]]) or "/" not in home[d["id"]]):
                continue                                                   # on a shared host, a root homepage (github.com) owns no story: users' repos aren't GitHub's news
            if count.get(k, 0) >= PER_KIND:
                continue
            if it["date"] and when(it["date"]) >= cutoff and it["url"] not in seen:
                count[k] = count.get(k, 0) + 1
                seen.add(it["url"])
                items.append({"id": d["id"], "name": names.get(d["id"], d["id"]), "kind": {"changelog": "changelog", "blog": "blog", "release": "release", "hn": "hacker news"}[k],
                              "title": title, "url": it["url"], "date": when(it["date"]),
                              **({"version": it["title"]} if kind == "release" and summary else {}),
                              **({"points": it["points"], "discussion": it["discussion"]} if kind == "hn" else {})})
    items.sort(key=lambda x: (x["date"], x["id"]), reverse=True)
    data = {"source": {"read": days[-1], "window_days": DAYS, "note": "Each item is the vendor's own announcement (its feed, linking to its own site), a GitHub release, "
                       "or a Hacker News story linking to the product's own site. Titles and release summaries are the publishers' own; bare version tags are omitted."}, "items": items}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    from collections import Counter
    print(f"news.json: {len(items)} items in {DAYS} days from {len({i['id'] for i in items})} products ({dict(Counter(i['kind'] for i in items))}), read {days[-1]}")

if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--fetch", action="store_true"); args = a.parse_args()
    if args.fetch:
        fetch()
    build()
