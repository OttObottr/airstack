# spec: AS-291
"""graph.json: what each product's own pages say it works with, as a directed graph, and the data a related(tool) answer needs.

An edge is a vendor's claim, never a check: "A says it integrates with B", with the page of A's that says so, the page's own words and
the day the page was read. Nothing here calls a model or the network; it reads files the other builders already wrote:
  claims      profiles.json (and the meeting-notes apps in market-data.js): the integration names shown on each product's page
  evidence    chain-data.json: per name, the page that names it, its quote, the page's class and the days it was read and re-read
  names       site-data.js index and data/catalog.json (names, aliases, domains), data/universe.json (homepages), directory.json (Wikidata, CC0)
  related     site-data.js and market-data.js (what a platform plan covers, meeting notes only), oss.json (open-source candidates)

How a name becomes a link (the first rule that finds anything decides; two different products there = ambiguous, left as text):
  1. name      the name of a product AirStack lists (catalog, registry or a checked app), any case, punctuation ignored
  2. alias     one of a catalog product's aliases, the same way
  3. domain    a name written as a web address whose host is the one catalog or registry product's own domain
  4. wikidata  a Wikidata product label, exactly, case kept (so "Edge" is not EDGE, a graphics program)
A name that is also a maker's name (Google, Meta, Oracle) links only by rule 1 or 4, never by an alias or a domain. Names that more than
one product goes by (WORDS below, found by reading the pages that use them) are never linked. Everything else stays text, as written.

Only pages chain-data.json ties to the product (its own site, a store listing it controls, its maker's documentation) make edges; a
name found only on a page not yet tied to the vendor is counted, not drawn. Usage: ../.venv/bin/python tools/build_graph.py
(after build_market_data.py and build_chain_data.py, so the claims and their evidence are the same day's)."""
import json, re, unicodedata
from airstack import paths

ROOT = paths.ROOT
from airstack.publication import hold                                      # noqa: E402

OWN = {"vendor", "store", "maker"}                                         # chain-data.json classes that are the product's own word
MEET = {"Google": "Google Meet", "Zoom": "Zoom", "Microsoft": "Microsoft Teams"}   # the platform each plan family's notes run in
WORDS = {                                                                  # names more than one product goes by, as read in context:
    "spark": "Apache Spark on data pages; the catalog's alias is Spark Mail",
    "bamboo": "Atlassian Bamboo on CI pages; the catalog's alias is BambooHR",
    "hive": "Apache Hive on data pages; the catalog lists Hive, a project tool",
    "falcon": "a Python web framework on server pages; the catalog's alias is CrowdStrike Falcon",
    "firefly": "a chemistry package on science pages; the catalog's alias is Adobe Firefly",
    "cognito": "Amazon Cognito on sign-in pages; the catalog's alias is Cognito Forms",
    "proton": "Valve's Proton on gaming pages; the catalog's alias is Proton Mail",
    "motion": "Apple Motion on video pages; the catalog lists Motion, a calendar tool",
    "writer": "LibreOffice Writer on office pages; the catalog lists Writer, an AI company",
    "muse": "a catalog alias of Meta's model API, and a common word",
    "unity": "the Unity game engine on 3D pages; Wikidata's Unity is Ubuntu's desktop",
    "sage": "Sage accounting on finance pages; Wikidata's Sage is SageMath",
    "epic": "Epic's games store or health records; Wikidata's Epic is a browser",
    "arena": "a chess program on chess pages; Wikidata's Arena is a 1990s browser",
    "sugar": "SugarCRM on sales pages; Wikidata's Sugar is a desktop for schools",
    "chrome": "Google Chrome; Wikidata's Chrome is Chromecast's",
    "calendar": "Google's or Apple's, depending on the page",
    "photos": "Google's or Apple's, depending on the page",
    "messages": "Google's or Apple's, depending on the page",
    "terminal": "any terminal; Wikidata's Terminal is macOS's",
    "sms": "text messages; Wikidata's SMS is a water-modelling program",
    "office": "any office suite",
    "make": "Make (make.com) on automation pages; GNU Make on build pages",
    "sentry": "Sentry on developer pages; an aviation receiver on ForeFlight's",
    "notes": "Apple's, Google's or any notes app", "contacts": "Apple's, Google's or any address book",
    **{w: "Wikidata's item of that name is a different program from the one the pages mean"
       for w in ("orca", "psi", "comet", "ciao", "planet", "swift", "vault", "sonar", "origin", "agora", "hermes", "anaconda", "pulse", "instant",
                 "swarm", "karbon")},
}
KINDS = {
    "covered_by": {"label": "Covered by", "available": "meeting notes only",
                   "means": "A platform plan you may already pay for takes notes too, as its maker's own help pages say."},
    "integrates_with": {"label": "Says it works with", "available": True,
                        "means": "The product's own page names the other product as an integration. The vendor's claim: AirStack has not tried it."},
    "named_by": {"label": "Named by", "available": True, "means": "Other products' own pages that name this one as an integration."},
    "alternative": {"label": "Alternatives", "available": "catalog categories and registry lanes",
                    "means": "AirStack lists both in the same category. AirStack's grouping, not a vendor claim and not a ranking."},
    "open_source": {"label": "Open-source candidates", "available": "the catalog's business categories",
                    "means": "Projects found through the category's GitHub topics that pass the licence and activity gate (oss.json). "
                             "Vetted means OpenSSF Scorecard's automated checks pass: not an audit."},
    "seen_together": {"label": "Seen together", "available": False,
                      "means": "Not available. AirStack stores no observation of products used together. Integration lists and comparison "
                               "pages are claims, never co-adoption."},
}

def key(s):
    """Any case, punctuation and marks ignored: 'MS Teams', 'ms-teams' and 'MS Teams®' are one key."""
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", str(s)).lower())

def label(s):
    """Exactly as written, case kept: only spacing, curly quotes and trademark signs are evened out."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(s)).replace("’", "'")).strip(" ®™")

def host(u):
    return re.split(r"[/?#:]", re.sub(r"^www\.", "", re.sub(r"^https?://", "", str(u or "").strip().lower())))[0]

DOMAIN = re.compile(r"(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+/?")

def resolver(index, tools, catalog, universe, directory):
    """resolve(name) -> (product id or None, the rule that decided or why it stays text)."""
    tiers = {t: {} for t in ("name", "alias", "domain", "wikidata")}
    def add(tier, k, pid):
        if k: tiers[tier].setdefault(k, set()).add(pid)
    for r in index: add("name", key(r[1]), r[0])
    for t in tools:
        add("name", key(t["name"]), t["key"])
        for a in t["aliases"]: add("alias", key(a), t["key"])
    for c in catalog:
        for a in c.get("aliases") or []: add("alias", key(a), c["id"])
        add("domain", c.get("domain"), c["id"]); add("domain", host(c["homepage"]), c["id"])
    for u in universe: add("domain", host(u.get("homepage")), u["id"])
    for p in directory["products"]: add("wikidata", label(p[1]), p[0])
    makers = {key(c["vendor"]) for c in catalog if c.get("vendor")} | {key(o[0]) for o in directory["orgs"].values() if o[5] != "person"}

    def resolve(name):
        k = key(name)
        if not k:
            return None, "not a name"
        if k in WORDS:
            return None, "names more than one product"
        site = host(name) if DOMAIN.fullmatch(name.strip().lower()) else None
        for tier, q in (("name", k), ("alias", k), ("domain", site), ("wikidata", label(name))):
            if q and not (k in makers and tier in ("alias", "domain")) and q in tiers[tier]:
                ids = tiers[tier][q]
                return (next(iter(ids)), tier) if len(ids) == 1 else (None, "ambiguous")
        return None, "names a maker" if k in makers else "not listed"
    return resolve

def claims(profiles, vendors):
    """product id -> the integration names its page shows, in the page's order."""
    out = {k: list(map(str, p["integrations"]["value"])) for k, p in profiles.items() if p.get("integrations")}
    for v in vendors:                                                      # the meeting-notes apps: their page shows the named list
        if v.get("integrations") and v["integrations"]["value"]["named"]:
            out[v["id"]] = list(map(str, v["integrations"]["value"]["named"]))
    return out

def build():
    site, market = paths.read_js(paths.SITE_DATA), paths.read_js(paths.MARKET_DATA)
    profiles = json.loads(paths.PROFILES.read_text())
    chain = json.loads(paths.CHAIN_DATA.read_text())["entities"]
    catalog = json.loads(paths.CATALOG.read_text())
    universe = json.loads(paths.UNIVERSE.read_text())
    directory = json.loads(paths.DIRECTORY.read_text())
    oss = json.loads(paths.OSS.read_text())
    resolve = resolver(site["index"], site["tools"], catalog, universe, directory)

    lanes = {c["id"]: c["name"] for c in site["cats"]} | {l["id"]: l["name"] for l in site["lanes"]}
    lane_of = {r[0]: r[2] for r in site["index"]} | {t["key"]: next((i for i, n in lanes.items() if n == t["cat"]), None) for t in site["tools"]}
    names = {p[0]: p[1] for p in directory["products"]} | {r[0]: r[1] for r in site["index"]} | {t["key"]: t["name"] for t in site["tools"]}
    names |= {e: x["name"] for e, x in chain.items() if e not in names}
    cat_ids, reg_ids = {c["id"] for c in catalog}, {u["id"] for u in universe}
    listed_as = lambda i: "catalog" if i in cat_ids else "registry" if i in reg_ids else "directory" if re.fullmatch(r"Q\d+", i) else "checked app"

    products, counts = {}, {"names": 0, "linked": 0, "text": {}, "by_rule": {}, "withheld_page_not_tied": 0, "self": 0}
    node = lambda i: products.setdefault(i, {"name": names.get(i, i), "lane": lane_of.get(i), "listed_as": listed_as(i),
                                             "pages": [], "integrates_with": [], "named_by": []})
    for pid, said in sorted(claims(profiles, market["vendors"]).items()):
        facts = [f for f in (chain.get(pid) or {}).get("facts", []) if f["metric"] == "integrations"]
        for n in said:
            counts["names"] += 1
            found = [f for f in facts if n.strip().lower() in {str(v).strip().lower() for v in f["value"]}]
            own = [f for f in found if f["class"] in OWN]
            if not own:
                counts["withheld_page_not_tied"] += 1; continue           # no own page names it: counted, never drawn
            target, how = resolve(n)
            if target == pid:
                counts["self"] += 1; continue
            me = node(pid)
            refs = []
            for f in own:
                page = {"url": f["url"], "class": f["class"], "quote": f["quote"], "read": f["retrieved"], "verified": f["verified"],
                        "recheck": f["recheck"] and {"at": f["recheck"]["at"], "outcome": f["recheck"]["outcome"]}}
                if page not in me["pages"]: me["pages"].append(page)
                refs.append(me["pages"].index(page))
            me["integrates_with"].append([n, target, sorted(set(refs))] + ([] if how == "not listed" else [how]))   # the rule that linked it, or why it is text
            if target:
                counts["linked"] += 1; counts["by_rule"][how] = counts["by_rule"].get(how, 0) + 1
                if pid not in node(target)["named_by"]: node(target)["named_by"].append(pid)
            else:
                counts["text"][how] = counts["text"].get(how, 0) + 1
    for p in products.values():
        p["named_by"].sort()
        p["counts"] = {"names": len(p["integrates_with"]), "linked": len({e[1] for e in p["integrates_with"] if e[1]}), "named_by": len(p["named_by"])}
        if not p["pages"]: del p["pages"], p["integrates_with"]
    hubs = sorted(((i, p["name"], p["counts"]["named_by"]) for i, p in products.items() if p["counts"]["named_by"]), key=lambda h: (-h[2], h[1], h[0]))
    unlisted = {}
    for p in products.values():
        for e in p.get("integrates_with", []):
            if not e[1] and len(e) == 3: unlisted[label(e[0])] = unlisted.get(label(e[0]), 0) + 1

    # ---- related(tool): the other four kinds, each from where AirStack already keeps it -----------------------------------------------
    gate = lambda r: r["gate"] is None                                   # below the gate: listed apart in oss.json, never an alternative
    checked = {c["id"]: (c.get("checked") or {}).get("date") for c in catalog}
    categories = {}
    for lid, lname in sorted(lanes.items()):
        members = sorted({r[0] for r in site["index"] if r[2] == lid} | {t["key"] for t in site["tools"] if lane_of[t["key"]] == lid})
        categories[lid] = {"name": lname, "from": "catalog" if lid in {c["id"] for c in site["cats"]} else "registry", "members": members,
                           "checked": max((checked[m] for m in members if checked.get(m)), default=None),
                           "open_source": [{"repo": r["repo"], "url": r["url"], "license": r["license"], "pushed": r["pushed"], "vetted": r["vetted"],
                                            "scorecard": r["scorecard"] and {"score": r["scorecard"]["score"], "date": r["scorecard"]["date"], "url": r["scorecard"]["url"]}}
                                           for r in oss["categories"].get(lid, []) if gate(r)]}
    edges, by_tool = [], {}
    def ref(e):
        if e not in edges: edges.append(e)
        return edges.index(e)
    for t in site["tools"]:
        mine = []
        for fam, plans in sorted(market["platforms"].items()):
            for plan, rule in plans.items():
                r = rule.get("online")
                if r and r["status"] == "covered":
                    mine.append(ref({"by": MEET[fam], "by_id": resolve(MEET[fam])[0], "plan": plan, "meeting": "online", "why": r["why"],
                                     "changes_if": r["changesIf"], "sources": [{k: r["source"][k] for k in ("url", "quote", "checked")}],
                                     "evaluated_at": r["evaluatedAt"], "fresh_until": r["freshUntil"]}))
        for plan, by_device in site["answers"][t["key"]].items():
            for device, i in by_device.items():
                a = site["pool"][i]
                if a["action"] == "retire":
                    mine.append(ref({"by": MEET["Google"], "by_id": resolve(MEET["Google"])[0], "plan": plan, "meeting": "in_person", "device": device,
                                     "why": a["reason"], "changes_if": a["changesIf"],
                                     "sources": [{"url": s["url"], "label": s["label"], "checked": s["date"], "published": s["published"]} for s in a["sources"]],
                                     "evaluated_at": a["evaluatedAt"], "fresh_until": a["freshUntil"]}))
        by_tool[t["key"]] = mine

    ds = directory["source"]
    data = {"source": {
                "claims_from": "profiles.json and the meeting-notes apps in market-data.js: the integration names each product's own pages show",
                "evidence_from": "chain-data.json: the page that names each one, its quote and the days it was read and re-read",
                "names_from": {"catalog": "data/catalog.json and site-data.js (AirStack's catalog and registry)",
                               "wikidata": f"{ds['name']} ({ds['license']}), read {ds['fetched_at'][:10]}"},
                "rule": ["name: a product AirStack lists, by its name, any case", "alias: one of a catalog product's aliases",
                         "domain: a web address that is one catalog or registry product's own domain", "wikidata: a Wikidata product label, exactly, case kept",
                         "the first rule that finds anything decides; two products there is ambiguous, left as text",
                         "a maker's name (Google, Meta, Oracle) links only by name or Wikidata label",
                         "names more than one product goes by are never linked (see words)",
                         "only pages tied to the product (its site, its store listing, its maker's documentation) make edges",
                         "a link made by a Wikidata label is a match of names, not of identity: it needs a second look"],
                "columns": {"integrates_with": ["the name as the page writes it", "the product it links to, or null", "indexes into pages",
                                                "the rule that linked it, or why it stays text (absent: AirStack does not list it)"]},
                "words": WORDS,
                "counts": counts,
                "open_source_from": {k: oss["source"][k] for k in ("name", "url", "fetched_at")} | {"checks": {k: oss["source"]["checks"][k] for k in ("name", "url", "license", "license_url", "fetched_at")}},
                "covered_by_from": "site-data.js and market-data.js: each platform plan checked against its maker's own help pages",
                "note": "An edge is what the product's own page says, not a test that the integration works. Named by counts products whose "
                        "pages name this one: a vendor claim, not usage and not market share."},
            "kinds": KINDS,
            "products": dict(sorted(products.items())),
            "hubs": [list(h) for h in hubs[:25]],
            "not_listed": sorted(([n, c] for n, c in unlisted.items() if c >= 3), key=lambda x: (-x[1], x[0]))[:100],
            "related": {"categories": categories, "covered_by": {"edges": edges, "by_tool": by_tool}}}
    return hold(data)

def main():
    data = build()
    paths.GRAPH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    c = data["source"]["counts"]
    print(f"graph.json: {c['names']} names on {sum(1 for p in data['products'].values() if 'pages' in p)} products' own pages; {c['linked']} linked "
          f"({', '.join(f'{k} {v}' for k, v in sorted(c['by_rule'].items()))}); {sum(c['text'].values())} kept as text; "
          f"{c['withheld_page_not_tied']} only on pages not tied to the vendor; top hubs {', '.join(f'{h[1]} ({h[2]})' for h in data['hubs'][:5])}; "
          f"{paths.GRAPH.stat().st_size // 1024} KB")
    return data

if __name__ == "__main__":
    main()
