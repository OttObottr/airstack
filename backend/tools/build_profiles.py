# spec: AS-055 AS-137 AS-248 AS-263 AS-327
"""Product profiles for every tool in the universe, researched by Muse Spark from each product's own pages.

Same gate as the market corpus (backend/airstack/corpus.py): code fetches (cached, conditional) -> shells refused -> Muse `profile`
extracts facts with verbatim quotes (memoised: an input is paid for once) -> code verifies each quote, list item and number on the page.
Calls run in a small thread pool; every call still reserves its maximum in the account ledger first.

Usage:  ../.venv/bin/python tools/build_profiles.py                 # replay from the memo: $0
        ../.venv/bin/python tools/build_profiles.py --live --cap 15 [--limit N] [--workers 4] [--lanes a,b]
        ../.venv/bin/python tools/build_profiles.py --catalog [--only id,id] --live --cap 25   # the mainstream catalog (data/catalog.json): its checked pages
        ../.venv/bin/python tools/build_profiles.py --directory 3000 --live --cap 30   # the best-known directory listings (directory.json): homepages
--cap is this database's day and lifetime cap; the separate private account ceiling and one-run authorization apply as well."""
import argparse, json, sys, threading
from concurrent.futures import ThreadPoolExecutor
from airstack.budget import BudgetGuard, BudgetExceeded
from airstack.corpus import Corpus, chunks
from airstack.fetch import UA, get as fetch_get
from airstack.spark import FakeSpark, GuardedSpark, ReplayMiss, memo_key
from airstack.config import MODEL
from airstack.store import Store, utcnow
from airstack import paths

ROOT = paths.ROOT
DB = paths.MARKET_DB
UNIVERSE = paths.UNIVERSE
CATALOG = paths.CATALOG
DIRECTORY = paths.DIRECTORY
SKIP_LANES = {"meeting-notes"}              # already researched by build_market.py with the meeting-notes vocabulary
PAGE_KINDS = ("home", "pricing", "docs", "integrations", "security")

def pages_for(tool, kinds=PAGE_KINDS):
    pages = [("home", tool.get("homepage"))] + [(k, (tool.get("pages") or {}).get(k)) for k in PAGE_KINDS[1:]]
    seen, out = set(), []
    for k, u in pages:
        if u and u not in seen and k in kinds:
            seen.add(u); out.append((k, u))
    return out

def catalog_tools(only=None):
    """Catalog entries in the shape run() takes: only entries whose homepage was reached and named the product (tools/check_catalog.py)."""
    out = []
    for e in json.loads(CATALOG.read_text()):
        ck = e.get("checked") or {}
        if not ck.get("title_matches") or (only and e["id"] not in only):
            continue
        out.append({"id": e["id"], "name": e["name"], "lane": e["category"], "homepage": e["homepage"],
                    "pages": {"pricing": e.get("pricing"), **{k: v for k, v in (e.get("pages") or {}).items() if v}}})   # docs, integrations, security: each checked live
    return out

def directory_tools(top, start=0):
    """The best-known directory listings (Wikidata, ranked by Wikipedia and sister-site pages), homepage only: the website Wikidata records.
    `start` skips the listings an earlier run already read (they would only replay from the memo)."""
    d = json.loads(DIRECTORY.read_text())
    return [{"id": p[0], "name": p[1], "lane": "directory", "homepage": p[3], "pages": {}} for p in d["products"][start:top] if p[3]]

def run(spark, store, corpus, now, tools, workers=1, fetch=None, kinds=PAGE_KINDS):
    rep = {"tools": 0, "pages": 0, "shells": [], "calls": 0, "cached": 0, "produced": 0, "admitted": 0, "rejected": [], "stopped": None,
           "incomplete": False}
    lock, stop = store._lock, threading.Event()                              # the store's own lock: every statement on the shared connection
    for t in tools:
        store.ensure_entity(t["id"], kind="product", name=t["name"], lane_id=t["lane"])
    jobs = [(t, k, u) for t in tools for k, u in pages_for(t, kinds)]
    def page(job):
        t, kind, url = job
        if stop.is_set():
            return
        with lock:
            have = corpus.c.execute("SELECT status, text, fetched_at FROM raw_items WHERE url=?", (url,)).fetchone()
        pg = {"url": url, "status": have[0], "text": have[1], "fetched_at": have[2], "shell": have[0] != 200 or len(have[1] or "") < 500} if have \
            else corpus_fetch(corpus, url, now, fetch, kind, lock)
        with lock:
            rep["pages"] += 1
            if pg["shell"]:
                rep["shells"].append(url); return
        for i, text in enumerate(chunks(pg["text"])):
            if stop.is_set():
                return
            payload = {"product": t["name"], "page_kind": kind, "page_url": url, "part": i + 1, "text": text}
            with lock:
                was = corpus.get(memo_key("profile", payload, getattr(spark.inner, "model_for", lambda r: MODEL)("profile"))) is not None
            try:
                res = spark.call("profile", payload, tool=t["id"])
            except ReplayMiss:
                with lock:
                    rep["rejected"].append((url, "call not in the offline memo")); rep["stopped"] = "replay_miss"; rep["incomplete"] = True
                stop.set(); return
            except BudgetExceeded as ex:
                with lock:
                    if ex.reason == "input_too_large":                      # one page too big to send: skip it and say so; only a real budget stop ends the batch
                        rep["rejected"].append((url, "page part too large to send")); rep["incomplete"] = True; continue
                    rep["stopped"] = rep["stopped"] or f"{ex.reason}: stopped before {url}"
                    rep["incomplete"] = True
                stop.set(); return
            except Exception as ex:
                with lock:
                    rep["rejected"].append((url, f"call failed: {type(ex).__name__}")); rep["incomplete"] = True
                continue
            with lock:
                rep["cached" if was else "calls"] += 1
                rep["produced"] += len(res.data["facts"])
                ok, bad = corpus.admit(t["id"], pg, res.data["facts"], res.call_id, now, kind)
                rep["admitted"] += len(ok); rep["rejected"] += [(url, f"{m}: {w}") for m, w in bad]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(page, jobs))
    for t in tools:
        spark.guard.end_tool(t["id"])
    rep["tools"] = len(tools)
    return rep

def corpus_fetch(corpus, url, now, fetch, kind, lock):
    status, body, hdrs = (fetch or fetch_get)(url, {"User-Agent": UA, "Accept-Language": "en-US,en"})
    from airstack.corpus import page_text
    import hashlib
    text = page_text(body) if status == 200 else ""
    with lock:
        corpus.c.execute("INSERT OR REPLACE INTO raw_items(url,status,fetched_at,etag,last_modified,body_hash,text,kind) VALUES(?,?,?,?,?,?,?,?)",
                         (url, status, now, hdrs.get("etag"), hdrs.get("last-modified"), hashlib.sha256(body.encode()).hexdigest(), text, kind))
    return {"url": url, "status": status, "text": text, "fetched_at": now, "shell": status != 200 or len(text) < 500}

def main(argv=None):
    a = argparse.ArgumentParser(); a.add_argument("--live", action="store_true"); a.add_argument("--cap", default="15"); a.add_argument("--day-cap", help="at most this much today (default: --cap); the daily job passes 0.25")
    a.add_argument("--limit", type=int); a.add_argument("--workers", type=int, default=4); a.add_argument("--lanes")
    a.add_argument("--kinds", default=",".join(PAGE_KINDS), help="which pages to read: home,pricing,docs,integrations,security")
    a.add_argument("--catalog", action="store_true", help="research data/catalog.json instead of the registry universe")
    a.add_argument("--directory", type=int, metavar="N", help="research the N best-known directory listings' homepages (directory.json)")
    a.add_argument("--from", dest="start", type=int, default=0, help="with --directory: start at this rank (skip listings already read)")
    a.add_argument("--only", help="comma-separated ids")
    args = a.parse_args(argv)
    only = set(args.only.split(",")) if args.only else None
    if args.directory:
        tools = [t for t in directory_tools(args.directory, args.start) if not only or t["id"] in only]
    elif args.catalog:
        tools = catalog_tools(only)
    else:
        tools = [t for t in json.loads(UNIVERSE.read_text()) if t["lane"] not in SKIP_LANES and (not args.lanes or t["lane"] in args.lanes.split(",")) and (not only or t["id"] in only)]
    tools = tools[: args.limit] if args.limit else tools
    store = Store(str(DB)); store._c.execute("PRAGMA busy_timeout=30000"); corpus = Corpus(store); now = utcnow()
    if args.live:
        import preflight; preflight.load_env(ROOT / ".env")
        from airstack.spark import LiveSpark
        inner = LiveSpark()
    else:
        inner = FakeSpark({}, cost="0", model=MODEL, replay_only=True)
    guard = BudgetGuard(store, utcnow, job_cap="0.50", day_cap=args.day_cap or args.cap, total_cap=args.cap, tool_calls=40, tool_searches=0)
    spark = GuardedSpark(inner, store, guard, utcnow, memo=corpus)
    rep = run(spark, store, corpus, now, tools, workers=args.workers if args.live else 1, kinds=tuple(args.kinds.split(",")))
    rate = rep["admitted"] / rep["produced"] if rep["produced"] else 0
    from collections import Counter
    print(json.dumps({**{k: v for k, v in rep.items() if k not in ("rejected", "shells")}, "shells": len(rep["shells"]), "pass_rate": round(rate, 3),
                      "rejections": Counter(w.split(": ", 1)[-1] for _, w in rep["rejected"]).most_common(6)}, indent=1))
    return rep

if __name__ == "__main__":
    sys.exit(1 if main().get("incomplete") else 0)
