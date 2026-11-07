# spec: AS-140 AS-263
"""Re-check the market corpus against the live web, with no model: the "re-checked" link of every claim's chain of custody.

For each page that backs an admitted fact: a conditional GET (304 means the server says it is unchanged since we read it); otherwise the
page is fetched again and every admitted quote is looked for on it. One row per page goes to `rechecks`. A failed fetch is recorded as a failure
and never counts as a successful check. The stored page text is NEVER replaced here: the memo's keys were computed from it, and a changed page
is a new input that needs a new extraction, not a silent edit of an old one.

Usage: ../.venv/bin/python tools/reverify_corpus.py [--limit N] [--workers 8] [--check]     (--check exits 1 if any quote went missing)"""
import argparse, hashlib, json, sys
from concurrent.futures import ThreadPoolExecutor
from airstack.corpus import Corpus, UA, norm, page_text
from airstack.fetch import get
from airstack.store import Store, utcnow
from airstack import paths

ROOT = paths.ROOT
DB = paths.MARKET_DB

def pages(corpus):
    """(url, [admitted quotes]) for every page that backs at least one admitted fact."""
    rows = corpus.c.execute("""SELECT f.url, p.quote FROM facts f JOIN fact_provenance p ON p.fact_id = f.id WHERE f.source = 'muse.catalog'""").fetchall()
    out = {}
    for url, quote in rows:
        out.setdefault(url, set()).add(quote)
    return {u: sorted(q) for u, q in out.items()}

def check_one(url, quotes, old, fetch):
    """Network only (runs in a worker thread). Returns the outcome row, without touching the database."""
    headers = {"User-Agent": UA, "Accept-Language": "en-US,en"}
    if old and old["etag"]: headers["If-None-Match"] = old["etag"]
    if old and old["last_modified"]: headers["If-Modified-Since"] = old["last_modified"]
    status, body, _ = (fetch or get)(url, headers)
    if status == 304:
        return {"url": url, "status": 304, "outcome": "unchanged", "body_hash": old["body_hash"], "quotes_total": len(quotes), "quotes_ok": len(quotes),
                "note": "the server reports the page unchanged since it was read"}
    if status != 200:
        return {"url": url, "status": status, "outcome": "fetch_failed", "body_hash": None, "quotes_total": len(quotes), "quotes_ok": None,
                "note": f"HTTP {status or 'no response'}: nothing was re-checked"}
    h = hashlib.sha256(body.encode()).hexdigest()
    text = norm(page_text(body))
    ok = sum(1 for q in quotes if norm(q) in text)
    same = old is not None and h == old["body_hash"]
    outcome = "unchanged" if same else ("changed_quotes_present" if ok == len(quotes) else "changed_quotes_missing")
    note = "byte-for-byte the same page" if same else (f"the page changed; all {len(quotes)} quotes are still on it" if ok == len(quotes)
                                                       else f"the page changed; {len(quotes) - ok} of {len(quotes)} quotes are no longer on it")
    return {"url": url, "status": 200, "outcome": outcome, "body_hash": h, "quotes_total": len(quotes), "quotes_ok": ok, "note": note}

def run(corpus, now, fetch=None, workers=8, limit=None, todo=None, record=True):
    todo = list(todo if todo is not None else pages(corpus).items())[:limit]          # todo: [(url, quotes)], e.g. the scheduler's due pages
    olds = {u: (lambda r: {"etag": r[0], "last_modified": r[1], "body_hash": r[2]} if r else None)(
        corpus.c.execute("SELECT etag, last_modified, body_hash FROM raw_items WHERE url=?", (u,)).fetchone()) for u, _ in todo}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda t: check_one(t[0], t[1], olds[t[0]], fetch), todo))
    if not record:                                                         # the scheduler keeps its log in data/rechecks/ instead (AS-263)
        return results
    with corpus.store._lock:
        for r in results:
            corpus.c.execute("INSERT INTO rechecks(url, checked_at, status, outcome, body_hash, quotes_total, quotes_ok, note) VALUES(?,?,?,?,?,?,?,?)",
                             (r["url"], now, r["status"], r["outcome"], r["body_hash"], r["quotes_total"], r["quotes_ok"], r["note"]))
    return results

def summary(results):
    from collections import Counter
    c = Counter(r["outcome"] for r in results)
    return {"pages": len(results), **c, "quotes_checked": sum(r["quotes_ok"] or 0 for r in results), "quotes_total": sum(r["quotes_total"] for r in results)}

def main(argv=None):
    a = argparse.ArgumentParser(); a.add_argument("--limit", type=int); a.add_argument("--workers", type=int, default=8); a.add_argument("--check", action="store_true")
    args = a.parse_args(argv)
    store = Store(str(DB)); corpus = Corpus(store)
    res = run(corpus, utcnow(), workers=args.workers, limit=args.limit)
    s = summary(res)
    print(json.dumps(s, indent=1))
    for r in res:
        if r["outcome"] in ("changed_quotes_missing", "fetch_failed"):
            print(f"  {r['outcome']:24} {r['url'][:90]}  {r['note']}")
    return 1 if args.check and s.get("changed_quotes_missing") else 0

if __name__ == "__main__":
    sys.exit(main())
