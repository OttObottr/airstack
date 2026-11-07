# spec: AS-250 AS-274
"""List prices from each catalog product's own pricing page: Standard-mode Muse Spark reads the stored page text
and returns each plan's price as written with a quote; code keeps a price only when its quote is on the page and contains the price.
Writes pricing.json (public): the sourced list prices the page may show. No other price reaches the screen.

Usage:  ../.venv/bin/python tools/build_pricing.py                                  # replay from the memo: $0
        ../.venv/bin/python tools/build_pricing.py --live --cap 50 [--workers 16]"""
import argparse, json, re, sys, threading
from concurrent.futures import ThreadPoolExecutor
from airstack.budget import BudgetGuard, BudgetExceeded
from airstack.config import MODEL
from airstack.corpus import Corpus, chunks, page_text
from airstack.fetch import published
from airstack.files import atomic_write_text
from airstack.publication import public_prices
from airstack.spark import FakeSpark, GuardedSpark, ReplayMiss
from airstack.store import Store, utcnow
from airstack import paths

ROOT = paths.ROOT
OUT = paths.PRICING
MONEY = re.compile(r"[$€£¥]\s?\d|\d[\d.,]*\s?(usd|eur|gbp)\b", re.I)
norm = lambda s: re.sub(r"\s+", " ", s or "").strip().lower()

def verify(page, plans):
    """Keep a plan only when its quote is on the page, the quote contains the price as written, the price states a currency,
    and the plan is named in the quote or within 120 characters before it."""
    text, ok, bad = norm(page), [], []
    for p in plans:
        q, price = norm(p["quote"]), norm(p["price"])
        at = text.find(q)
        if at < 0: bad.append((p, "quote not on the page")); continue
        if len(q.split()) > 25: bad.append((p, "quote longer than 25 words")); continue
        if price.replace(" ", "") not in q.replace(" ", ""): bad.append((p, "price not in its quote")); continue
        if not MONEY.search(p["price"]): bad.append((p, "no currency")); continue
        if norm(p["plan"]) not in text[max(0, at - 120):at + len(q)]: bad.append((p, "plan not named beside its price")); continue
        ok.append({k: p[k] for k in ("plan", "price", "period", "unit", "quote")})
    return ok, bad

PAGES = paths.PRICING_PAGES                               # discovered pricing pages: {id: url}, with how each was found
LINK = re.compile(r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
PRICEY = re.compile(r"\b(pricing|plans?(?: (?:and|&) pricing)?|prices?|compare plans|editions)\b", re.I)

def discover(targets, corpus, now, workers=16):
    """Each target's own pricing page, free: a Pricing/Plans link on its homepage that stays on its own site, else /pricing when
    that page names a currency. The page is stored like any other (kind 'pricing'); the URL and how it was found go to PAGES."""
    import urllib.parse, urllib.request
    from concurrent.futures import ThreadPoolExecutor as TP
    host = lambda u: (urllib.parse.urlsplit(u).hostname or "").lower().removeprefix("www.")
    from airstack.fetch import get as _get                                  # one honest name; robots.txt obeyed (AS-274)
    def get(u):
        status, body, h = _get(u, {"Accept": "text/html"}, timeout=15)
        return status, body[:2_000_000], h.get("x-final-url", u)
    def find(t):
        st, body, final = get(t["homepage"])
        if st != 200:
            return t["id"], None, None
        h = host(final); cands = []
        for href, text in LINK.findall(body[:400000]):
            label = re.sub(r"<[^>]+>|\s+", " ", text).strip()
            u = urllib.parse.urljoin(final, href)
            if len(label) <= 40 and PRICEY.search(label) and (host(u) == h or host(u).endswith("." + h)) and u.startswith("http"):
                cands.append((0 if "pric" in u.lower() else 1, len(u), u))
        if cands:
            return t["id"], sorted(cands)[0][2], "homepage link"
        u = f"{urllib.parse.urlsplit(final).scheme}://{urllib.parse.urlsplit(final).netloc}/pricing"
        st, body, final2 = get(u)
        return (t["id"], final2, "/pricing") if st == 200 and MONEY.search(page_text(body)) else (t["id"], None, None)   # readable text: a "$" in a script is not a price
    known = json.loads(PAGES.read_text()) if PAGES.exists() else {}
    todo = [t for t in targets if t["id"] not in known]
    with TP(workers) as ex:
        for i, url, how in ex.map(find, todo):
            known[i] = {"url": url, "how": how, "checked": now[:10]}
    PAGES.write_text(json.dumps(dict(sorted(known.items())), ensure_ascii=False, indent=0))
    found = [t | {"pricing": known[t["id"]]["url"]} for t in targets if (known.get(t["id"]) or {}).get("url")]
    from airstack.fetch import get as fetch_get
    have = {u for (u,) in corpus.c.execute("SELECT url FROM raw_items WHERE kind='pricing' AND status=200")}
    need = [t["pricing"] for t in found if t["pricing"] not in have]
    with TP(workers) as ex:                                                # the network in parallel; the database one page at a time (one connection)
        got = dict(zip(need, ex.map(lambda u: fetch_get(u, {"Accept-Language": "en-US,en"}), need)))
    for u in need:
        corpus.fetch(u, now, fetch=lambda url, headers, r=got[u]: r, kind="pricing")
    corpus.c.commit()
    return found

def publish(prices, path=None):
    """Atomically replace the public projection; private/raw extraction records are never copied through unfiltered."""
    safe = public_prices(prices)
    atomic_write_text(path or OUT, json.dumps(dict(sorted(safe.items())), ensure_ascii=False, separators=(",", ":")))
    return safe

def main(argv=None):
    a = argparse.ArgumentParser(); a.add_argument("--live", action="store_true")
    a.add_argument("--cap", default="50"); a.add_argument("--workers", type=int, default=8); a.add_argument("--only", help="comma-separated ids (a pilot)")
    a.add_argument("--discover", action="store_true", help="also find and read the pricing pages of every researched product (directory and catalog) that has none")
    args = a.parse_args(argv)
    only = set(args.only.split(",")) if args.only else None
    from airstack.catalog import entries
    store = Store(str(paths.MARKET_DB)); store._c.execute("PRAGMA busy_timeout=30000"); corpus = Corpus(store)
    if args.live:
        import preflight; preflight.load_env(ROOT / ".env")
        from airstack.spark import LiveSpark
        inner = LiveSpark()
    else:
        inner = FakeSpark({}, cost="0", model=MODEL, replay_only=True)
    guard = BudgetGuard(store, utcnow, job_cap="0.50", day_cap=args.cap, total_cap=args.cap, tool_calls=40, tool_searches=0)
    spark = GuardedSpark(inner, store, guard, utcnow, memo=corpus); lock = store._lock; stop = threading.Event()
    out, rep = {}, {"pages": 0, "calls": 0, "kept": 0, "refused": 0, "errors": [], "stopped": None}
    def page(e):
        if stop.is_set(): return
        if not published(e["pricing"]):
            return                                                        # an explicit publication hold, not an incomplete build
        with lock:
            row = corpus.c.execute("SELECT text, fetched_at FROM raw_items WHERE url=? AND status=200", (e["pricing"],)).fetchone()
        if not row or len(row[0] or "") < 500:
            with lock: rep["errors"].append(f"{e['id']}: pricing page is not in the readable corpus")
            return
        plans = []
        for i, part in enumerate(chunks(row[0])):
            if stop.is_set(): return
            payload = {"product": e["name"], "page_url": e["pricing"], "part": i + 1, "text": part}
            opened = False
            try:
                if args.live:
                    with lock:
                        guard.begin_tool(e["id"], purpose=f"pricing:{e['id']}", dedupe_key=None); opened = True
                res = spark.call("pricing", payload, tool=e["id"])
            except ReplayMiss:
                with lock: rep["errors"].append(f"{e['id']}: part {i + 1} is not in the memo")
                stop.set(); return
            except BudgetExceeded as ex:
                with lock:
                    rep["errors"].append(f"{e['id']}: part {i + 1} refused ({ex.reason})")
                    rep["stopped"] = rep["stopped"] or ex.reason
                if ex.reason != "input_too_large": stop.set()
                return
            except Exception as ex:
                with lock: rep["errors"].append(f"{e['id']}: part {i + 1} failed ({type(ex).__name__})")
                return
            finally:
                if opened:
                    with lock: guard.end_tool(e["id"])
            ok, bad = verify(row[0], res.data["plans"])
            with lock: rep["calls"] += 1; rep["kept"] += len(ok); rep["refused"] += len(bad)
            plans += ok
        seen, uniq = set(), []
        for p in plans:
            k = (norm(p["plan"]), norm(p["price"]), p["period"])
            if k not in seen: seen.add(k); uniq.append(p)
        with lock:
            rep["pages"] += 1
            if uniq: out[e["id"]] = {"url": e["pricing"], "checked": (row[1] or "")[:10], "plans": uniq}
    todo = [e for e in entries() if e.get("pricing") and (not only or e["id"] in only)]
    if args.discover:                                                      # every researched product without a known pricing page, best documented first
        profiles = json.loads(paths.PROFILES.read_text()); D = json.loads(paths.DIRECTORY.read_text())
        have = {e["id"] for e in todo}
        cat = [e | {"homepage": e["homepage"]} for e in entries() if e["id"] not in have and e.get("homepage") and e["id"] in profiles]
        dirs = [{"id": p[0], "name": p[1], "homepage": p[3]} for p in sorted(D["products"], key=lambda p: -p[6]) if p[0] in profiles and p[3]]
        todo += discover(cat + dirs, corpus, utcnow())
    with ThreadPoolExecutor(args.workers if args.live else 1) as ex:
        list(ex.map(page, todo))
    if rep["errors"] or rep["stopped"]:
        print(json.dumps({**rep, "products_with_prices": None}))
        return 1                                                        # leave the previous public file byte-for-byte intact
    if only or args.discover:                                                            # a pilot adds to the published file, never replaces it
        prev = json.loads(OUT.read_text()) if OUT.exists() else {}; out = {**prev, **out}
    out = {k: {**v, "plans": [q for q in v["plans"] if len(q["quote"].split()) <= 25]} for k, v in out.items() if published(v["url"])}   # AS-274
    out = {k: v for k, v in out.items() if v["plans"]}
    out = publish(out)
    print(json.dumps({**rep, "products_with_prices": len(out)}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
