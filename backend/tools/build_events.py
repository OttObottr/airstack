# spec: AS-298
"""events.json: one factual table of what happened and dates a source published, for the calendar and market map.

Every event has a status, and the status is the honesty axis:
- observed: it happened and there is a record (a vendor's changelog or release, an HN story linking to its site, a page AirStack
  re-read and found changed, a support cycle that has ended).
- scheduled: the vendor's published schedule names the date (an end of life or end of support, from endoflife.date, MIT).
- recheck: AirStack's own monitoring date for reviewing the supporting evidence again.
Every entry is a sourced day. Release forecasts and inferred cadence windows do not belong in this factual calendar.
No model call. endoflife.date responses are saved per day (data/eol-raw/), and the build repeats offline.

Usage: ../.venv/bin/python tools/build_events.py --fetch    # read endoflife.date, then build
       ../.venv/bin/python tools/build_events.py            # rebuild events.json from what is saved"""
import argparse, gzip, json, re, sys, time, urllib.request
from datetime import date, datetime, timedelta, timezone
from airstack import paths
from airstack.fetch import UA

ROOT = paths.ROOT
RAW, OUT = paths.DATA / "eol-raw", paths.EVENTS
API = "https://endoflife.date/api"
PAST, AHEAD = 365, 730
key = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=20) as r:
        return json.loads(r.read(5_000_000))

def fetch():
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d"); out = {"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "api": API, "products": {}}
    for slug in get(f"{API}/all.json"):
        if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", slug):
            try:
                out["products"][slug] = get(f"{API}/{slug}.json")
            except Exception:
                continue
            time.sleep(0.25)                                               # polite: about four requests a second
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{day}.json.gz").write_bytes(gzip.compress(json.dumps(out, sort_keys=True).encode(), mtime=0))

def iso(v):
    return v if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else None

def main():
    a = argparse.ArgumentParser(); a.add_argument("--fetch", action="store_true"); args = a.parse_args()
    if args.fetch:
        fetch()
    site = (lambda t: json.loads(t[t.index("{"):t.rindex("}") + 1]))(paths.SITE_DATA.read_text())
    D = json.loads(paths.DIRECTORY.read_text()); catalog = json.loads(paths.CATALOG.read_text())
    names = {r[0]: r[1] for r in site["index"]} | {p[0]: p[1] for p in D["products"]}
    by_name = {}
    for pid, nm in sorted(names.items(), key=lambda kv: kv[0]):
        by_name.setdefault(key(nm), pid)
    for c in catalog:
        for a_ in [c["name"], *c.get("aliases", [])]:
            by_name.setdefault(key(a_), c["id"])
    news = json.loads(paths.NEWS.read_text()) if paths.NEWS.exists() else {"items": [], "source": {"read": None}}
    today = date.fromisoformat(news["source"]["read"]) if news["source"].get("read") else date.today()
    lo, hi = (today - timedelta(days=PAST)).isoformat(), (today + timedelta(days=AHEAD)).isoformat()
    ev = []
    for i in news["items"]:                                                # observed: the vendor's own feed, releases, HN stories on its site
        ev.append({"id": i["id"], "name": i["name"], "at": i["date"][:10], "precision": "day", "status": "observed", "kind": i["kind"], "title": i["title"], "url": i["url"]})
    days = sorted(RAW.glob("????-??-??.json.gz")) if RAW.exists() else []
    eol = json.loads(gzip.decompress(days[-1].read_bytes())) if days else {"products": {}}
    matched = 0
    for slug, cycles in sorted(eol["products"].items()):                   # scheduled: the published support schedule of products AirStack lists
        pid = by_name.get(key(slug)) or by_name.get(key(slug.replace("-", " ")))
        if not pid or not isinstance(cycles, list):
            continue
        matched += 1
        for c in cycles[:12]:
            for field, what in (("eol", "end of life"), ("support", "end of active support"), ("extendedSupport", "end of extended support")):
                d = iso(c.get(field))
                if d and lo <= d <= hi:
                    ev.append({"id": pid, "name": names.get(pid, slug), "at": d, "precision": "day", "status": "observed" if d <= today.isoformat() else "scheduled",
                               "kind": what, "title": f"{names.get(pid, slug)} {c.get('cycle')}: {what}", "url": f"https://endoflife.date/{slug}"})
    for k, a_ in sorted(site.get("answers", {}).items()) if isinstance(site.get("answers"), dict) else []:
        pass
    s = json.dumps(site)
    for m in sorted(set(re.findall(r'"fresh_until": "(\d{4}-\d{2}-\d{2})', s))):   # AirStack's own monitoring schedule
        ev.append({"id": "meeting-notes", "name": "Meeting-notes evidence", "at": m, "precision": "day", "status": "recheck", "kind": "answer recheck",
                   "title": "The meeting-notes evidence is scheduled for review by this day", "url": "https://airstack.bot/#/record"})
    ev = [e for e in ev if lo <= e["at"] <= hi]
    ev.sort(key=lambda e: (e["at"], e["status"], e["id"], e["kind"]))
    data = {"source": {"built_for": today.isoformat(), "window": [lo, hi], "support_schedules": {"name": "endoflife.date", "url": "https://endoflife.date/", "license": "MIT", "read": eol.get("fetched_at", "")[:10] or None},
                       "statuses": {"observed": "it happened, with its record", "scheduled": "a source published this date", "recheck": "AirStack's own review date"}},
            "events": ev}
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    from collections import Counter
    print(f"events.json: {len(ev)} events ({dict(Counter(e['status'] for e in ev))}); endoflife.date matched {matched} products")

if __name__ == "__main__":
    sys.exit(main())
