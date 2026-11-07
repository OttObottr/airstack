# spec: AS-140 AS-233 AS-238 AS-348
"""Writes ../chain-data.json: the chain of custody for every verified fact in the market corpus, loaded lazily by the page's evidence inspector.

Per fact, in order: the source page and what kind of source it is -> when it was retrieved and its content hash -> when it was extracted
and the page's own words -> when code verified those words on the page -> the latest live re-check -> which other pages state the same thing.
Agreement is counted separately for sources independent of the vendor, and says "none" when there are none: only vendor-origin pages are not corroboration.
`registry` lists what the vendor's own package registry or GitHub repository states for the same value (data/corroboration.json, written by
corroborate.py): a second record from the same origin, counted apart and never in `agree` or `agree_independent`. A dispute stays visible.
Nothing here calls a model or the network. Usage: ../.venv/bin/python tools/build_chain_data.py"""
import json, sqlite3
from collections import defaultdict
from build_market_data import CURRENCY, host, day
from airstack import paths
from airstack.policy import blocked_ids, display_name
from airstack.publication import latest_rechecks, missing_quote_urls

ROOT = paths.ROOT
DB = paths.MARKET_DB
CORROBORATION = paths.DATA / "corroboration.json"     # optional: without it every fact has registry == []
REGISTRY_LABELS = {"registry_second_record": "matches a second record (vendor-published registry)", "registry_disputed": "disputed by a registry record"}
STORES = {"chromewebstore.google.com", "apps.apple.com", "play.google.com"}
MAKER_DOCS = {"zoom": ("zoom.com", "zoom.us", "support.zoom.com"), "teams": ("learn.microsoft.com", "support.microsoft.com", "microsoft.com")}
LIST_METRICS = ("x.joins_meeting_apps", "x.devices", "x.integrations", "x.compliance", "x.plan_names", "x.notes_plans", "x.deployment", "x.platforms", "x.sdk_languages", "x.models_supported")
INDEPENDENT = {"9to5google.com"}                     # hosts positively known to be third parties; nothing else is ever counted as independent
SOURCE_CLASS = {"vendor": "the vendor's own site", "store": "a store listing the vendor controls", "maker": "the platform maker's own documentation",
                "independent": "an independent source", "other": "a domain not yet tied to the vendor (not counted as independent)"}

def registrable(h):
    parts = h.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else h

def source_class(entity, url, homepages):
    h = host(url)
    if h in STORES:
        return "store"
    if any(h == d or h.endswith("." + d) for d in MAKER_DOCS.get(entity, ())):
        return "maker"
    home = homepages.get(entity)
    if home and registrable(host(home)) == registrable(h):
        return "vendor"
    return "independent" if h in INDEPENDENT else "other"            # unknown is never independent

def registry_records(corroboration=None):
    """(entity, metric, value as JSON) -> the vendor's own registry records for that claim value."""
    if corroboration is None:
        corroboration = json.loads(CORROBORATION.read_text()) if CORROBORATION.exists() else {}
    return {(c["tool"], c["metric"], json.dumps(c["value"], sort_keys=True)): c["registry"] for c in corroboration.get("claims", [])}

def build(db=DB, universe=None, corroboration=None):
    universe = universe if universe is not None else json.loads(paths.UNIVERSE.read_text())
    registry = registry_records(corroboration)
    from build_market import PAGES                      # the meeting-notes apps use their own ids; their home pages are listed there
    homepages = {t["id"]: t["homepage"] for t in universe} | {e: u for e, kind, u in PAGES if kind == "home"}
    catalog = json.loads(paths.CATALOG.read_text()) if paths.CATALOG.exists() else []
    directory = json.loads(paths.DIRECTORY.read_text()) if paths.DIRECTORY.exists() else {"products": []}
    homepages = {p[0]: p[3] for p in directory["products"] if p[3]} | {c["id"]: c["homepage"] for c in catalog if c.get("homepage")} | homepages   # every product's own site, so its own pages count as the vendor's
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    c.row_factory = sqlite3.Row
    pages = {r["url"]: dict(r) for r in c.execute("SELECT url, status, fetched_at, body_hash FROM raw_items")}
    rechecks = latest_rechecks(c, successful_only=True)                       # database and append-only daily logs, one publication rule
    extracted_at = {r["call_ref"]: r["ts"] for r in c.execute("SELECT call_ref, ts FROM calls WHERE kind != 'cached'")}
    names = {r["id"]: display_name(r["id"], r["name"]) for r in c.execute("SELECT id, name FROM entities")}
    rows = c.execute("""SELECT f.entity_id e, f.metric m, f.value v, f.url, p.call_ref, p.quote, v2.checked_at vchecked
                        FROM facts f JOIN fact_provenance p ON p.fact_id = f.id
                        LEFT JOIN verifications v2 ON v2.url = f.url AND v2.metric = f.metric AND v2.quote = p.quote AND v2.call_ref = p.call_ref AND v2.ok = 1
                        WHERE f.source = 'muse.catalog' ORDER BY f.entity_id, f.metric, f.id""").fetchall()
    from airstack.corpus import failing_now, is_bad
    bad = failing_now(c)
    rows = [r for r in rows if not is_bad(bad, r["url"], r["quote"], r["m"])]      # admitted under older rules, rejected by today's: not in the chain
    missing = missing_quote_urls(c)
    rows = [r for r in rows if r["url"] not in missing]                            # the page changed and no longer carries every published quote
    rows = [r for r in rows if r["e"] not in blocked_ids()]                         # not listed or published (airstack.policy)
    by_value = defaultdict(lambda: defaultdict(set))        # (entity, metric) -> item-or-value -> urls
    for r in rows:
        v = json.loads(r["v"])
        for item in (v if r["m"] in LIST_METRICS and isinstance(v, list) else [json.dumps(v, sort_keys=True)]):
            by_value[(r["e"], r["m"])][str(item).strip().lower()].add(r["url"])
    out = {}
    for r in rows:
        v = json.loads(r["v"])
        if CURRENCY.search(json.dumps(v) + r["quote"]):
            continue                                        # no price reaches the screen, even here
        items = [str(x).strip().lower() for x in v] if r["m"] in LIST_METRICS and isinstance(v, list) else [json.dumps(v, sort_keys=True)]
        scalar_text = r["m"] in ("x.what_it_does", "x.license", "x.pricing_basis", "x.customers_claimed")   # the value is this page's own words: agreement is not defined
        other = set().union(*[by_value[(r["e"], r["m"])][i] for i in items]) - {r["url"]} if not scalar_text else set()
        cls = lambda u: source_class(r["e"], u, homepages)
        pg, rc = pages.get(r["url"], {}), rechecks.get(r["url"])
        out.setdefault(r["e"], {"name": names.get(r["e"], r["e"]), "facts": []})["facts"].append({
            "metric": r["m"][2:], "value": v, "url": r["url"], "host": host(r["url"]), "class": cls(r["url"]), "quote": r["quote"],
            "retrieved": day(pg.get("fetched_at")), "status": pg.get("status"), "hash": (pg.get("body_hash") or "")[:12],
            "extracted": extracted_at.get(r["call_ref"]), "verified": day(r["vchecked"]) or None,
            "recheck": ({"at": day(rc["checked_at"]), "outcome": rc["outcome"], "note": rc["note"]} if rc else None),
            "agree": sorted({host(u) for u in other}), "agree_independent": sorted({host(u) for u in other if cls(u) == "independent"}),
            "registry": [rec for x in (v if isinstance(v, list) else [v]) for rec in registry.get((r["e"], r["m"][2:], json.dumps(x, sort_keys=True)), [])]})
    facts = [f for e in out.values() for f in e["facts"]]
    summary = {"facts": len(facts), "registry_second_record": sum(bool(f["registry"]) and all(x["agrees"] for x in f["registry"]) for f in facts),
               "registry_disputed": sum(any(not x["agrees"] for x in f["registry"]) for f in facts), "labels": REGISTRY_LABELS,
               "registry_note": "A package registry entry or GitHub repository is published by the same vendor: a second record from the same origin, "
                                "not independent confirmation. A fact any registry record disputes counts as disputed, not as a match. "
                                "A fact listing several values counts as a match when at least one value is shown and none is disputed; "
                                "each record's `claim` names the value it matched."}
    return {"classes": SOURCE_CLASS, "summary": summary, "entities": out}

def main():
    data = build()
    paths.CHAIN_DATA.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    n = sum(len(e["facts"]) for e in data["entities"].values())
    s = data["summary"]
    print(f"chain-data.json: {len(data['entities'])} entities, {n} facts, {paths.CHAIN_DATA.stat().st_size // 1024} KB; "
          f"{s['registry_second_record']} match a second record (vendor-published registry), {s['registry_disputed']} disputed by a registry record")
    return data

if __name__ == "__main__":
    main()
