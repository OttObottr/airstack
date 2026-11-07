# spec: AS-263
"""The freshness scheduler: what to re-check now, so the corpus stays current as it grows, at the lowest cost.

Every page that backs a fact or a list price gets a tier, the time it was last checked, and an interval that learns from its own
history: halved after a check found it changed, doubled after two unchanged checks in a row, doubled again after four (bounded at
half and four times the tier's base). Due pages are ordered by how overdue they are, weighted by tier and by demand (registry
downloads, Wikipedia-family pages). Then, in two stages:

1. Free: a conditional GET of each due page (304 or the same bytes: unchanged), and every stored quote looked for again
   (reverify_corpus). Most pages end here; a check that finds every quote moves the page's "checked" date, nothing else.
2. Paid, only with --live and the owner's cap: pages whose text changed AND lost a quote are re-extracted by Standard-mode Muse Spark,
   memoised on the new text, through the account ledger. The budget caps how many; the rest wait for tomorrow.

freshness.json (public, no spend figures): per tier, how many pages, the median and 95th-percentile age, and the share inside
its interval. The plan's projected model calls and their cost are printed here only.

Usage: ../.venv/bin/python tools/refresh.py                 # the plan: due pages per tier, projected calls (free, read-only)
       ../.venv/bin/python tools/refresh.py --check 2000    # stage 1 on the 2,000 most overdue pages (free: re-fetch, re-find quotes)
       ../.venv/bin/python tools/refresh.py --publish       # write freshness.json"""
import argparse, gzip, json, math, sqlite3, statistics, sys
from datetime import datetime, timezone
from airstack import paths

ROOT = paths.ROOT
DB = paths.MARKET_DB
LOG = paths.DATA / "rechecks"                                           # one small file a day: the free checks never touch the private database

def logged():
    """Re-check rows from the daily files, oldest first: (url, checked_at, outcome, ...)."""
    for f in sorted(LOG.glob("*.jsonl.gz")) if LOG.exists() else []:
        for line in gzip.decompress(f.read_bytes()).decode().splitlines():
            yield json.loads(line)
TIERS = {"pricing": (7, 4.0), "catalog": (14, 2.0), "directory": (30, 1.0)}   # base interval in days, priority weight
DAY = 86400

def ts(s):
    return datetime.strptime(s[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp() if s else None

def interval(base, history):
    """The page's own interval from its recheck outcomes, oldest first."""
    if not history:
        return base
    if history[-1].startswith("changed"):
        return base / 2
    streak = 0
    for o in reversed(history):
        if o != "unchanged":
            break
        streak += 1
    return base * (4 if streak >= 4 else 2 if streak >= 2 else 1)

def plan(now=None):
    now = now or datetime.now(timezone.utc).timestamp()
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    catalog = {e["id"] for e in json.loads(paths.CATALOG.read_text())}
    links = {p[0]: p[6] for p in json.loads(paths.DIRECTORY.read_text())["products"]}
    pricing = json.loads(paths.PRICING.read_text())
    quotes, owner = {}, {}
    for url, quote, eid in c.execute("SELECT f.url, p.quote, f.entity_id FROM facts f JOIN fact_provenance p ON p.fact_id = f.id"):
        quotes.setdefault(url, set()).add(quote); owner[url] = eid
    for eid, q in pricing.items():
        for pl in q["plans"]:
            quotes.setdefault(q["url"], set()).add(pl["quote"]); owner[q["url"]] = eid
    fetched = {u: ts(f) for u, f in c.execute("SELECT url, fetched_at FROM raw_items")}
    hist = {}
    rows_ = [(u, at, o) for u, at, o in c.execute("SELECT url, checked_at, outcome FROM rechecks WHERE outcome != 'fetch_failed' ORDER BY checked_at, id")]
    rows_ += sorted((r["url"], r["checked_at"], r["outcome"]) for r in logged() if r["outcome"] != "fetch_failed")
    for u, at, o in sorted(rows_, key=lambda r: r[1]):
        hist.setdefault(u, []).append(o); fetched[u] = max(fetched.get(u) or 0, ts(at))
    rows = []
    for url, qs in quotes.items():
        eid = owner[url]
        tier = "pricing" if any(q["url"] == url for q in [pricing.get(eid, {"url": None})]) else "catalog" if eid in catalog else "directory"
        base, weight = TIERS[tier]
        iv = interval(base, hist.get(url, [])) * DAY
        last = fetched.get(url) or 0
        age = now - last
        demand = 1 + math.log10(1 + links.get(eid, 0))
        rows.append({"url": url, "entity": eid, "tier": tier, "quotes": sorted(qs), "age_days": age / DAY, "interval_days": iv / DAY,
                     "due": age >= iv, "priority": (age / iv) * weight * demand})
    rows.sort(key=lambda r: -r["priority"])
    calls = c.execute("SELECT COUNT(*), AVG(CAST(cost AS REAL)) FROM calls WHERE role='profile'").fetchone()
    outcomes = {}
    for _, _, o in rows_:
        outcomes[o] = outcomes.get(o, 0) + 1
    return rows, {"mean_call_cost": calls[1] or 0.0003, "outcomes": outcomes}

def freshness(rows):
    out = {}
    for t in TIERS:
        r = [x for x in rows if x["tier"] == t]
        if not r:
            continue
        ages = sorted(x["age_days"] for x in r)
        out[t] = {"pages": len(r), "base_interval_days": TIERS[t][0], "median_age_days": round(statistics.median(ages), 1),
                  "p95_age_days": round(ages[int(0.95 * (len(ages) - 1))], 1), "within_interval": round(sum(1 for x in r if not x["due"]) / len(r), 3)}
    return out

def main(argv=None):
    a = argparse.ArgumentParser(); a.add_argument("--check", type=int, metavar="N", help="re-check the N most overdue due pages (free)")
    a.add_argument("--publish", action="store_true", help="write freshness.json"); a.add_argument("--workers", type=int, default=12)
    args = a.parse_args(argv)
    rows, m = plan()
    due = [r for r in rows if r["due"]]
    o = m["outcomes"]; seen = sum(o.values()) or 1
    lost = o.get("changed_quotes_missing", 0) / seen                       # the share of checks that would need a new extraction
    print(f"{len(rows):,} pages back facts or prices; {len(due):,} due now "
          + ", ".join(f"{t} {sum(1 for r in due if r['tier'] == t):,}" for t in TIERS))
    print(f"history: {seen:,} re-checks, {o.get('changed_quotes_present', 0) + o.get('changed_quotes_missing', 0):,} changed, {o.get('changed_quotes_missing', 0):,} lost a quote "
          f"-> about {lost * len(due):,.0f} re-extractions for today's due pages, ~${lost * len(due) * m['mean_call_cost']:.2f} at ${m['mean_call_cost']:.5f} a call "
          f"(a full re-read of every page would be ~${len(rows) * m['mean_call_cost']:.2f})")
    if args.check:
        from airstack.corpus import Corpus
        from airstack.store import Store, utcnow
        import reverify_corpus as rv
        store = Store(str(DB)); corpus = Corpus(store)
        now = utcnow()
        res = rv.run(corpus, now, workers=args.workers, todo=[(r["url"], r["quotes"]) for r in due[: args.check]], record=False)
        LOG.mkdir(parents=True, exist_ok=True); f = LOG / f"{now[:10]}.jsonl.gz"
        old = gzip.decompress(f.read_bytes()).decode() if f.exists() else ""
        f.write_bytes(gzip.compress((old + "".join(json.dumps({"checked_at": now, **r}, sort_keys=True) + "\n" for r in res)).encode(), mtime=0))
        print(json.dumps(rv.summary(res)))
        changed = sorted({r["url"] for r in res if r["outcome"] == "changed_quotes_missing"})
        ents = sorted({x["entity"] for x in rows if x["url"] in changed})
        (LOG / "lost-a-quote.txt").write_text(",".join(ents))                # the daily job's input for the paid stage
        if ents:
            print(f"{len(ents)} products lost a quote; re-extract with the owner's cap:\n  AIRSTACK_ACCOUNT_CAP_USD=<cap> .venv/bin/python backend/tools/build_profiles.py "
                  f"--live --only {','.join(ents)}")
        rows, _ = plan()
    if args.publish or args.check:
        f = freshness(rows)
        (paths.FRESHNESS).write_text(json.dumps({"tiers": f, "rule": "interval halves after a change and doubles after unchanged checks; "
                                                         "a page is re-extracted only when it lost a quote"}, separators=(",", ":")))
        print("freshness.json:", json.dumps(f))

if __name__ == "__main__":
    sys.exit(main())
