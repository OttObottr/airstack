# spec: AS-255
"""insights.json: market-level views computed from facts already quoted on each product's own pages, with every denominator stated.
No model call, no new research: a view of what is stored.

- map: every researched product placed by two measured inputs. x = how widely it is documented (Wikipedia and sister-site pages,
  from Wikidata, matched by item or by website). y = where AI appears in what its own pages say: in its one-line description;
  elsewhere on its pages (the models it names, the AI providers it says it integrates with, or AI in its plan names: a weaker claim,
  kept as its own band and labelled with its evidence); or not in what AirStack read. A product missing either input is counted as
  unplaced, never guessed. Each band states its count and the denominator.
  Founding year is not used: an old company can ship an AI-first product.
- categories: per business category, shares over the researched products in it (free plan stated, SOC 2 or ISO 27001 claimed,
  open source stated, AI in the one-liner, a public list price quoted), each with a buyer's label, its count and its denominator, the
  department the category serves (data/departments.json), the median product by starting price per user per month
  (a sourced list price, named and linked), and the tools its products most often say they integrate with.
- hubs: across everything researched, the products most often named in other products' own integration lists.

Usage: ../.venv/bin/python tools/build_insights.py"""
import json, re
from airstack import paths
from airstack.publication import public_prices

ROOT = paths.ROOT
import build_directory as bd                                               # noqa: E402  (its saved Wikidata responses and host())

PRICING, CFG = paths.config("pricing"), paths.config("insights")          # config/pricing.json, config/insights.json
ADDON = re.compile(PRICING["addon_pattern"], re.I)
MEDIAN_MIN = PRICING["median_min"]                                                     # a median of fewer products is one product's price, not a category's
PROVIDER = re.compile(CFG["provider_pattern"], re.I)
AI = re.compile(CFG["ai_pattern"], re.I)
key = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())

def ai_evidence(p):
    """Where AI appears on a product's own pages, strongest first: 'one-liner', then 'models', 'providers', 'plans'; [] when nowhere."""
    vals = lambda k: [str(v) for v in ((p.get(k) or {}).get("value") or [])] if isinstance((p.get(k) or {}).get("value"), list) else ([str(p[k]["value"])] if p.get(k) else [])
    out = []
    if p.get("what_it_does") and (AI.search(str(p["what_it_does"]["value"])) or PROVIDER.search(str(p["what_it_does"]["value"]))): out.append("one-liner")
    if p.get("models_supported"): out.append("models")
    if any(PROVIDER.search(v) for v in vals("integrations")): out.append("providers")
    if any(AI.search(v) or PROVIDER.search(v) for v in vals("plan_names")): out.append("plans")
    return out

def ai_role(p):
    ev = ai_evidence(p)
    if "one-liner" in ev:
        return 2                                                           # AI in its own one-line description
    if ev:
        return 1                                                           # AI elsewhere on its own pages: models, AI providers or AI plans it names
    return 0 if p.get("what_it_does") else None                           # not in what AirStack read; unknown without a one-liner

def cheapest_seat(q):
    """The lowest per-user-per-month list price in dollars on its pricing page, or None (other units and periods are not comparable)."""
    xs = []
    for p in q["plans"]:
        m = re.search(r"\$\s?(\d[\d,]*(?:\.\d+)?)", p["price"])
        if m and p["unit"] == "user" and p["period"] == "month" and float(m.group(1).replace(",", "")) > 0 and not ADDON.search(p["plan"] + " " + p.get("quote", "")):
            xs.append((float(m.group(1).replace(",", "")), p))
    return min(xs, key=lambda t: t[0]) if xs else None

def main():
    site = paths.read_js(paths.SITE_DATA); P = json.loads(paths.PROFILES.read_text()); Q = public_prices(json.loads(paths.PRICING.read_text()))
    D = json.loads(paths.DIRECTORY.read_text()); catalog = {c["id"]: c for c in json.loads(paths.CATALOG.read_text())}
    cats = {c["id"]: c["name"] for c in site["cats"]}
    names = {r[0]: r[1] for r in site["index"]} | {p[0]: p[1] for p in D["products"]}
    links = {p[0]: p[6] for p in D["products"]}
    addr = lambda u: (bd.host(u) + re.sub(r"^https?://[^/]+", "", u or "")).rstrip("/").lower()   # the same address, not the same host:
    by_addr = {}                                                           # github.com/features/copilot is not github.com
    for r in bd.raw_products():                                            # catalog products are left out of the directory, not out of Wikidata
        if r["site"]: by_addr[addr(r["site"])] = max(by_addr.get(addr(r["site"]), 0), r["links"])
    for pid, c in catalog.items():
        if c.get("homepage") and addr(c["homepage"]) in by_addr: links.setdefault(pid, by_addr[addr(c["homepage"])])
    lane = {r[0]: r[2] for r in site["index"]}
    # who is named where: a name, an alias or a website host resolves to a product AirStack lists
    resolve = {}
    for pid, c in catalog.items():
        for a in [c["name"], *c.get("aliases", [])]: resolve.setdefault(key(a), pid)
    for pid, nm in names.items(): resolve.setdefault(key(nm), pid)

    pts, unplaced = [], 0
    for pid, p in P.items():
        role, l = ai_role(p), links.get(pid)
        if role is None or not l:
            unplaced += 1; continue
        pts.append([pid, names.get(pid, pid), cats.get(lane.get(pid), ""), l, role, [e for e in ai_evidence(p) if e != "one-liner"]])
    pts.sort(key=lambda r: (-r[3], r[1]))

    hubs = {}
    for pid, p in P.items():
        for name in set(map(str, (p.get("integrations") or {}).get("value") or [])):
            t = resolve.get(key(name))
            if t and t != pid: hubs.setdefault(t, set()).add(pid)

    dept = json.loads((paths.DEPARTMENTS).read_text())
    out_c = {}
    for cid, cname in cats.items():
        ids = [i for i, c in catalog.items() if c["category"] == cid]; R = [i for i in ids if i in P]
        if not R:
            continue
        share = lambda f: sum(1 for i in R if f(P[i]))
        seats = sorted(((cheapest_seat(Q[i]), i) for i in R if i in Q and cheapest_seat(Q[i])), key=lambda t: t[0][0])
        med = seats[(len(seats) - 1) // 2] if len(seats) >= MEDIAN_MIN else None              # the lower median: a real product's real list price
        ww = {}
        for i in R:
            for name in set(map(str, (P[i].get("integrations") or {}).get("value") or [])):
                ww[key(name)] = ww.get(key(name), [name, 0]); ww[key(name)][1] += 1
        out_c[cid] = {"name": cname, "department": dept.get(cid), "listed": len(ids), "researched": len(R),
                      "free_plan": share(lambda p: (p.get("free_plan") or {}).get("value") is True),
                      "security_claim": share(lambda p: any(re.search(r"SOC ?2|ISO ?27001", str(v)) for v in (p.get("compliance") or {}).get("value") or [])),
                      "open_source": share(lambda p: (p.get("open_source") or {}).get("value") is True),
                      "ai_one_liner": share(lambda p: ai_role(p) == 2),
                      "list_price": sum(1 for i in R if i in Q),
                      "median_seat": {"id": med[1], "name": names.get(med[1], med[1]), "plan": med[0][1]["plan"], "price": med[0][1]["price"], "url": Q[med[1]]["url"],
                                      "of": len(seats)} if med else None,
                      "works_with": [[n, c, resolve.get(k)] for k, (n, c) in sorted(ww.items(), key=lambda kv: (-kv[1][1], kv[1][0]))[:8] if c >= 2]}
    data = {"source": {"facts_from": "profiles.json (quotes found on each product's own pages)", "documentation_from": D["source"]["name"] + ", read " + D["source"]["fetched_at"][:10],
                       "prices_from": "pricing.json (list prices quoted from pricing pages)",
                       "note": "x is documentation breadth, not market share; y is what a product's own pages say, not what it does. Unplaced products miss an input."},
            "map": {"axes": {"x": "Wikipedia and sister-site pages", "y": ["No AI in what we read", "AI elsewhere on its pages (models, AI providers or AI plans it names)", "AI in its one-line description"]},
                    "points": pts, "unplaced": unplaced, "researched": len(P),
                    "bands": [sum(1 for p in pts if p[4] == b) for b in (0, 1, 2)],
                    "populations": {"categories": [sum(1 for p in pts if p[4] == b and not p[0].startswith("Q")) for b in (0, 1, 2)],   # the products AirStack catalogs by category
                                    "all_listed": [sum(1 for p in pts if p[4] == b and p[0].startswith("Q")) for b in (0, 1, 2)]},       # everything else Wikidata lists, much of it older than AI
                    "elsewhere": {k: sum(1 for p in pts if p[4] == 1 and k in p[5]) for k in ("models", "providers", "plans")}},
            "kpis": [{"key": "free_plan", "label": "Free plan"}, {"key": "list_price", "label": "Prices read by AirStack"},
                     {"key": "security_claim", "label": "SOC 2 or ISO 27001"}, {"key": "open_source", "label": "Open source"},
                     {"key": "ai_one_liner", "label": "AI in its one-line description"}],
            "departments": sorted({v for v in dept.values()}),
            "categories": out_c,
            "hubs": [[t, names.get(t, t), len(s)] for t, s in sorted(hubs.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:24]]}
    paths.INSIGHTS.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    roles = [sum(1 for p in pts if p[4] == k) for k in (2, 1, 0)]
    print(f"insights.json: {len(pts)} placed ({roles[0]} AI one-liner, {roles[1]} AI elsewhere {data['map']['elsewhere']}, {roles[2]} no AI read), {unplaced} unplaced; "
          f"{len(out_c)} categories; top hubs {', '.join(f'{h[1]} ({h[2]})' for h in data['hubs'][:5])}")

if __name__ == "__main__":
    main()
