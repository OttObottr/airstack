# spec: AS-248 AS-317
"""The directory: every software product Wikidata (CC0) records with an official website, and the companies that make them.
Listed, not researched: each row is Wikidata's record (name, one-line description, website, developer, type), linked to its item.
Rows already in the catalog or the registry universe (same website host or name) are left to those. No model call, no cost.

Usage:  ../.venv/bin/python tools/build_directory.py --fetch    # query Wikidata, save every raw response in data/wikidata-raw/
        ../.venv/bin/python tools/build_directory.py            # rebuild directory.json offline, byte for byte, from the saved responses"""
import argparse, gzip, hashlib, json, re, urllib.parse, urllib.request
from airstack import paths, wikidata
from airstack.fetch import host, public_url
from airstack.wikidata import ENDPOINT, q, qid

ROOT = paths.ROOT
RAW, OUT = paths.DATA / "wikidata-raw", paths.DIRECTORY
SOFTWARE = "Q7397"
NOT_PRODUCTS = {"Q7889": "video game", "Q7058673": "video game series", "Q9143": "programming language", "Q188860": "software library",
                "Q271680": "software framework", "Q235557": "file format", "Q20826013": "software version", "Q317623": "technical standard",
                "Q165194": "application programming interface", "Q29642950": "Python package", "Q209163": "expansion add-on",
                "Q112144412": "esports discipline", "Q20825628": "GNU package", "Q193564": "game engine"}
BATCH = 150
ONLINE_SERVICE, WEBSITE = "Q19967801", "Q35127"
MAKER_CLASSES = {"Q1058914": "software company", "Q15911314": "internet company", "Q18388277": "technology company"}
NOT_SOFTWARE_SERVICE = re.compile(r"shop|store|retail|grocer|bookstore|travel agency|restaurant|food delivery|dating|gambling|casino|betting|pornograph", re.I)
POLICY = paths.config("excluded")                                          # what AirStack does not list: piracy, adult content, illegal markets, malware (config/excluded.json)
BLOCKED_TYPE, BLOCKED_TEXT = re.compile(POLICY["type_labels"], re.I), re.compile(POLICY["text"], re.I)
DEFUNCT = re.compile(r"\bformer(ly)?\b|\bdefunct\b|\bdiscontinued\b|\(\d{4}\s*[-–]\s*\d{4}\)", re.I)
WEB_MIN_LINKS = 3                                                          # a website or service needs Wikipedia-family pages in 3+ languages: the obscure ones were noise
NOT_A_PRODUCT_DESC = re.compile(r"\b(news|newspaper|magazine|blog|wiki|encyclopedia|fan ?site|radio|television|tv channel|government|ministry|"
                                r"university|college|school|museum|library|journal|newsletter|podcast|forum for fans|personal website|portal of|"
                                r"affiliate|broadcast|tv station|forums?|database of|species|loyalty program|academic publisher|archive|domain name|online resource|"
                                r"company|agency|organi[sz]ation|corporation|conglomerate)\b", re.I)

def sparql(name, query, refresh=False, tries=4):
    return wikidata.sparql(RAW, name, query, refresh, tries)

def fetch():
    classes = {qid(q(b, "c")) for b in sparql("classes", f"SELECT DISTINCT ?c WHERE {{ ?c wdt:P279* wd:{SOFTWARE} . }}")}
    for x in NOT_PRODUCTS:
        classes -= {qid(q(b, "c")) for b in sparql(f"not-{x}", f"SELECT DISTINCT ?c WHERE {{ ?c wdt:P279* wd:{x} . }}")}
    classes = sorted(classes)
    for i in range(0, len(classes), BATCH):
        vals = " ".join(f"wd:{c}" for c in classes[i:i + BATCH])
        sparql(f"products-{i // BATCH:03d}", f"""SELECT ?s ?name ?desc ?site ?links ?type (GROUP_CONCAT(DISTINCT ?dev; separator=" ") AS ?devs)
          (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases) (GROUP_CONCAT(DISTINCT ?other; separator=" ") AS ?types) WHERE {{
          VALUES ?type {{ {vals} }} ?s wdt:P31 ?type ; wdt:P856 ?site ; wikibase:sitelinks ?links ; rdfs:label ?name . FILTER(LANG(?name) = "en")
          ?s wdt:P31 ?other . OPTIONAL {{ ?s schema:description ?desc FILTER(LANG(?desc) = "en") }} OPTIONAL {{ ?s wdt:P178 ?dev }}
          OPTIONAL {{ ?s skos:altLabel ?alias FILTER(LANG(?alias) = "en") }} }} GROUP BY ?s ?name ?desc ?site ?links ?type""")
    sparql("products-meta", """SELECT ?s ?name ?desc ?site ?links ?type (GROUP_CONCAT(DISTINCT ?dev; separator=" ") AS ?devs)
      (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases) (GROUP_CONCAT(DISTINCT ?other; separator=" ") AS ?types) WHERE {
      ?s wdt:P178|wdt:P176 wd:Q380 ; wdt:P856 ?site ; wikibase:sitelinks ?links ; rdfs:label ?name . FILTER(LANG(?name) = "en")
      ?s wdt:P31 ?type . ?s wdt:P31 ?other . OPTIONAL { ?s schema:description ?desc FILTER(LANG(?desc) = "en") } OPTIONAL { ?s wdt:P178 ?dev }
      OPTIONAL { ?s skos:altLabel ?alias FILTER(LANG(?alias) = "en") } } GROUP BY ?s ?name ?desc ?site ?links ?type""")   # Meta's whole tree: what Meta develops or makes, whatever Wikidata types it as
    for i in range(0, len(classes), 1000):                                 # the taxonomy: every type's English name and its parent types
        sparql(f"types-{i // 1000:03d}", f"""SELECT ?c ?label ?parent WHERE {{ VALUES ?c {{ {" ".join(f"wd:{c}" for c in classes[i:i + 1000])} }}
          ?c rdfs:label ?label FILTER(LANG(?label) = "en") OPTIONAL {{ ?c wdt:P279 ?parent }} }}""")
    services = sorted({qid(q(b, "c")) for b in sparql("classes-svc", f"SELECT DISTINCT ?c WHERE {{ ?c wdt:P279* wd:{ONLINE_SERVICE} . }}")} - set(classes))
    sparql("types-svc", f"""SELECT ?c ?label ?parent WHERE {{ VALUES ?c {{ {" ".join(f"wd:{c}" for c in services + [WEBSITE])} }}
      ?c rdfs:label ?label FILTER(LANG(?label) = "en") OPTIONAL {{ ?c wdt:P279 ?parent }} }}""")
    sparql("products-svc-000", product_query(" ".join(f"wd:{c}" for c in services), "wdt:P178|wdt:P127"))   # SaaS that Wikidata files as a service, not as software
    sparql("software-companies", "SELECT DISTINCT ?o WHERE { ?o wdt:P31 wd:Q1058914 ; wdt:P856 ?w . }")
    sparql("tech-companies", f"SELECT DISTINCT ?o WHERE {{ VALUES ?k {{ {' '.join(f'wd:{k}' for k in MAKER_CLASSES)} }} ?o wdt:P31 ?k ; wdt:P856 ?w . }}")
    seen, rnd, frontier = set(), 0, all_makers(web=False)                 # the fan-out: every maker's websites, then the makers of those, until nothing new
    while frontier and rnd < 4:                                           # each round's makers come only from the round before, so saved batches stay aligned
        makers = sorted(frontier)
        for i in range(0, len(makers), 100):                              # 100 makers a query: 300 timed out at the public endpoint
            fan_out(f"products-web-r{rnd}-{i // 100:03d}", makers[i:i + 100])
        seen |= frontier
        frontier = makers_in(f"products-web-r{rnd}-") - seen; rnd += 1
    ids = sorted({r["id"] for r in raw_products()} - {None})              # end dates: a discontinued product or a shut-down service is not listed as current
    have = {m for k, v in saved().items() if k.startswith("ended-") for m in re.findall(r"wd:(Q\d+)", v["query"])}
    todo = [i for i in ids if i not in have]
    for i in range(0, len(todo), 400):
        sparql(f"ended-{len(list(RAW.glob('ended-*.json.gz'))):03d}", f"SELECT DISTINCT ?s WHERE {{ VALUES ?s {{ {' '.join(f'wd:{x}' for x in todo[i:i + 400])} }} ?s wdt:P2669|wdt:P576|wdt:P730|wdt:P3999 ?d . }}")
    devs = sorted(all_makers())
    asked = lambda prefix: {m for k, v in saved().items() if k.startswith(prefix) for m in re.findall(r"wd:(Q\d+)", v["query"])}   # makers already queried
    for name, size, make in [("orgs", 400, lambda ids: f"""SELECT ?o ?name ?site ?country ?founded WHERE {{ VALUES ?o {{ {ids} }}
          ?o rdfs:label ?name FILTER(LANG(?name) = "en") OPTIONAL {{ ?o wdt:P856 ?site }}
          OPTIONAL {{ ?o wdt:P17 ?c . ?c rdfs:label ?country FILTER(LANG(?country) = "en") }} OPTIONAL {{ ?o wdt:P571 ?founded }} }}"""),
                             ("employees", 400, lambda ids: f"SELECT ?o ?n ?when WHERE {{ VALUES ?o {{ {ids} }} ?o p:P1128 ?st . ?st ps:P1128 ?n . OPTIONAL {{ ?st pq:P585 ?when }} }}"),
                             ("org-links", 400, lambda ids: f"SELECT ?o ?l WHERE {{ VALUES ?o {{ {ids} }} ?o wikibase:sitelinks ?l . }}"),
                             ("businesses", 300, lambda ids: f"SELECT DISTINCT ?o WHERE {{ VALUES ?o {{ {ids} }} ?o wdt:P31/wdt:P279* wd:Q4830453 . }}"),
                             ("people", 500, lambda ids: f"SELECT ?o WHERE {{ VALUES ?o {{ {ids} }} ?o wdt:P31 wd:Q5 . }}")]:
        new = sorted(set(devs) - asked(f"{name}-"))                       # only makers not asked before: the first pass's saved batches stay as they are
        for i in range(0, len(new), size):
            sparql(f"{name}-fan-{i // size:03d}", make(" ".join(f"wd:{d}" for d in new[i:i + size])))

def fan_out(name, makers):
    """One maker batch's websites. A batch that times out is split in half until it answers; a single maker that still times out
    is skipped and named in the log (its websites stay unlisted), so one prolific publisher cannot stop the whole fan-out."""
    if (RAW / f"{name}.json.gz").exists() or not (any(RAW.glob(f"{name}a*.json.gz")) or any(RAW.glob(f"{name}b*.json.gz"))):
        try:
            return sparql(name, f"""SELECT ?s ?name ?desc ?site ?links ?type (GROUP_CONCAT(DISTINCT ?dev; separator=" ") AS ?devs)
              (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases) (GROUP_CONCAT(DISTINCT ?other; separator=" ") AS ?types) WHERE {{
              VALUES ?o {{ {" ".join(f"wd:{m}" for m in makers)} }} VALUES ?type {{ wd:{WEBSITE} }}
              ?s wdt:P178|wdt:P127|wdt:P123 ?o ; wdt:P31 ?type ; wdt:P856 ?site ; wikibase:sitelinks ?links ; rdfs:label ?name . FILTER(LANG(?name) = "en")
              ?s wdt:P31 ?other . OPTIONAL {{ ?s schema:description ?desc FILTER(LANG(?desc) = "en") }} OPTIONAL {{ ?s wdt:P178|wdt:P127|wdt:P123 ?dev }}
              OPTIONAL {{ ?s skos:altLabel ?alias FILTER(LANG(?alias) = "en") }} }} GROUP BY ?s ?name ?desc ?site ?links ?type""", tries=2)
        except RuntimeError as ex:
            if len(makers) == 1:
                print(f"skipped {makers[0]}: {ex}", flush=True); return []
    h = len(makers) // 2
    return fan_out(f"{name}a", makers[:h]) + fan_out(f"{name}b", makers[h:])

def product_query(vals, maker="wdt:P178"):
    return f"""SELECT ?s ?name ?desc ?site ?links ?type (GROUP_CONCAT(DISTINCT ?dev; separator=" ") AS ?devs)
      (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases) (GROUP_CONCAT(DISTINCT ?other; separator=" ") AS ?types) WHERE {{
      VALUES ?type {{ {vals} }} ?s wdt:P31 ?type ; wdt:P856 ?site ; wikibase:sitelinks ?links ; rdfs:label ?name . FILTER(LANG(?name) = "en")
      ?s wdt:P31 ?other . OPTIONAL {{ ?s schema:description ?desc FILTER(LANG(?desc) = "en") }} OPTIONAL {{ ?s {maker} ?dev }}
      OPTIONAL {{ ?s skos:altLabel ?alias FILTER(LANG(?alias) = "en") }} }} GROUP BY ?s ?name ?desc ?site ?links ?type"""

def makers_in(prefix):                                                    # a news site's publisher is not a software maker
    return {d for p in raw_products(prefix) if not NOT_A_PRODUCT_DESC.search(p["desc"] or "") for d in p["devs"]} - {None}

def all_makers(web=True):
    return ({d for p in raw_products() if (web or not p["web"]) and not NOT_A_PRODUCT_DESC.search(p["desc"] or "") for d in p["devs"]} | {qid(q(b, "o")) for b in load("software-companies")} | {qid(q(b, "o")) for b in load("tech-companies")}) - {None}

def saved():
    return {f.name[:-8]: json.loads(gzip.decompress(f.read_bytes())) for f in sorted(RAW.glob("*.json.gz"))}

def load(prefix):
    return [b for k, v in saved().items() if k.startswith(prefix) for b in v["results"]]

def raw_products(prefix="products-"):
    for k, v in saved().items():
        if not k.startswith(prefix):
            continue
        for b in v["results"]:
            yield product_row(b, k.startswith("products-web-"), k.startswith(("products-web-", "products-svc-")))

def product_row(b, web, fan=False):
    site = re.sub(r"^https?://", lambda m: m.group(0).lower(), q(b, "site") or "", flags=re.I)
    return {"id": qid(q(b, "s")), "name": POLICY["renames"].get(qid(q(b, "s")), q(b, "name")), "desc": q(b, "desc"), "site": site if public_url(site, resolve=False) else None,
            "links": int(q(b, "links") or 0), "type": qid(q(b, "type")), "devs": [d for d in map(qid, (q(b, "devs") or "").split()) if d],
            "types": set(map(qid, (q(b, "types") or "").split())) - {None}, "aliases": [a for a in (q(b, "aliases") or "").split("|") if a], "web": web, "fan": fan}

NOT_SOFTWARE_LABEL = re.compile(r"wiki|encyclopedia|repository|conference|video game|esports|\bmod\b", re.I)   # projects, archives and events typed as software
NOT_A_PAGE_NAME = re.compile(r"^(Module|Template|Category|User|Help):")
PER_PAGE = 100_000                                                        # employees one page about an organization can vouch for: real giants stay under half (DoD 2.87M on 60 pages, Accenture 779,000 on 51)

def implausible(kind, n, pages):
    """Why a recorded headcount is out of line with the organization's kind or documentation, or None (also when its pages are unknown).
    A person is not an employer. An organization's staff may not exceed 100,000 for each Wikipedia-family page about it, its Wikidata record
    counting as one: Fintech Band, a small firm recorded with 846,554 employees and no page, fails; Amazon (1.5M, 124 pages) does not."""
    if kind == "person":
        return "a person, not an employer"
    if pages is not None and n > PER_PAGE * (pages + 1):
        return f"out of line with its documentation: over {PER_PAGE * (pages + 1):,} employees with {pages} Wikipedia-family page{'' if pages == 1 else 's'}"

def build():
    excluded = {qid(q(b, "c")) for x in NOT_PRODUCTS for b in load(f"not-{x}")}
    labels, parents = {}, {}
    for b in load("types-"):
        c = qid(q(b, "c")); labels[c] = q(b, "label")
        if q(b, "parent"):
            parents.setdefault(c, set()).add(qid(q(b, "parent")))
    off_topic = excluded | {c for c, l in labels.items() if NOT_SOFTWARE_LABEL.search(l)}
    software = {qid(q(b, "c")) for b in saved()["classes"]["results"]} - excluded
    shops = {c for c, l in labels.items() if c not in software and NOT_SOFTWARE_SERVICE.search(l)}
    ended = {qid(q(b, "s")) for b in load("ended-")}                     # discontinued, dissolved, or service retired (Wikidata P2669, P576, P730, P3999)
    makers_ids = {qid(q(b, "o")) for b in load("orgs-")}                   # a maker found only by the website/service fan-out (Google, Meta Platforms) is an organization;
    classed = {r["id"] for r in raw_products() if not r["fan"]}            # one Wikidata item for company and product (Facebook, Spotify) stays a product as before   # a shop typed also as a website is still a shop             # a website or service is held to a stricter test (its description) than software
    known = json.loads(paths.UNIVERSE.read_text()) + json.loads(paths.CATALOG.read_text())
    taken_hosts = {host(t.get("homepage")) for t in known} - {""}
    key = lambda n: re.sub(r"[^a-z0-9]", "", n.lower())
    taken_names = {key(t["name"]) for t in known}
    best = {}
    blocked = lambda p: p["id"] in POLICY["ids"] or BLOCKED_TEXT.search(f'{p["name"]} {p["desc"] or ""}') or any(BLOCKED_TYPE.match(labels.get(t, "")) for t in p["types"] | {p["type"]})
    for p in raw_products():
        if (blocked(p) or p["types"] & off_topic or p["id"] in ended or (p["id"] in makers_ids and p["id"] not in classed) or p["links"] < 1 or not p["site"] or host(p["site"]) in taken_hosts or key(p["name"]) in taken_names
                or p["name"] == p["id"] or NOT_A_PAGE_NAME.match(p["name"]) or (p["type"] not in software and (NOT_A_PRODUCT_DESC.search(p["desc"] or "") or DEFUNCT.search(p["desc"] or "")
                    or p["links"] < WEB_MIN_LINKS or NOT_SOFTWARE_SERVICE.search(labels.get(p["type"], "")) or p["types"] & shops))):
            continue                                                       # at least one Wikipedia-family article: a record someone wrote up, not a stub
        p["type"] = p["type"] if p["type"] in labels else SOFTWARE          # a type with no English name reads as plain "software"
        cur = best.get(p["id"])
        if cur is None or (p["type"] != SOFTWARE and cur["type"] == SOFTWARE):    # one row per item; the most specific type wins over plain "software"
            best[p["id"]] = p
    rows, names, hosts = [], set(), set()
    for p in sorted(best.values(), key=lambda p: (p["type"] not in software, -p["links"], p["name"].lower(), p["id"])):   # software first: a same-name website never displaces it     # one listing per name and per website: the best-known record wins
        site = (host(p["site"]) + urllib.parse.urlsplit(p["site"]).path).rstrip("/").lower()   # the same address, not the same host: github.com holds thousands of products
        if key(p["name"]) in names or site in hosts:
            continue
        names.add(key(p["name"])); hosts.add(site); rows.append(p)
    makes = {}
    for p in rows:
        for d in set(p["devs"]) - {p["id"]}:
            makes[d] = makes.get(d, 0) + 1
    rows = [p for p in rows if makes.get(p["id"], 0) < 2]                  # one item for a company and its brand (Google, Q95): it makes 2+ listed products, so it opens as the maker
    rows.sort(key=lambda p: (-p["links"], p["name"].lower(), p["id"]))
    def up(c):                                                             # a type and every ancestor inside the software tree
        seen, todo = set(), [c]
        while todo:
            x = todo.pop()
            if x in seen or x not in labels:
                continue
            seen.add(x); todo += parents.get(x, ())
        return seen
    reach = {c: SOFTWARE in up(c) for c in labels}                          # a type whose parents never lead to "software" hangs from it directly
    lineage = lambda c: {a for a in up(c) if reach.get(a)} | {c, SOFTWARE}
    total, direct = {}, {}
    for p in rows:
        direct[p["type"]] = direct.get(p["type"], 0) + 1
        for a in lineage(p["type"]):
            total[a] = total.get(a, 0) + 1
    tids = sorted(total, key=lambda c: (-total[c], labels.get(c, c)))
    ix = {c: i for i, c in enumerate(tids)}
    orgs = {}
    for b in load("orgs-"):
        if BLOCKED_TEXT.search(q(b, "name") or ""):
            continue                                                       # an organization the policy does not list either
        o, candidate = qid(q(b, "o")), q(b, "site")
        candidate = candidate if public_url(candidate, resolve=False) else None
        cur = orgs.setdefault(o, {"name": q(b, "name"), "site": candidate, "country": q(b, "country"), "founded": (q(b, "founded") or "")[:4] or None})
        cur["site"] = cur["site"] or candidate; cur["country"] = cur["country"] or q(b, "country")
    made = {}
    for p in rows:
        for d in p["devs"]:
            made[d] = made.get(d, 0) + 1
    people = {qid(q(b, "o")) for b in load("people-")}
    business = {qid(q(b, "o")) for b in load("businesses-")}
    org_links = {qid(q(b, "o")): int(q(b, "l") or 0) for b in load("org-links-")}
    staff = {}
    for b in load("employees-"):                                          # the latest dated headcount; an undated one only when nothing is dated
        o, n, when = qid(q(b, "o")), q(b, "n"), (q(b, "when") or "")[:4]
        when = when if when.isdigit() else ""                              # an "unknown value" date is a URL, not a year
        try: n = int(float(n))
        except (TypeError, ValueError): continue
        if n > 0 and (o not in staff or (when, n) > (staff[o][1] or "", staff[o][0])): staff[o] = (n, when or None)
    keep = {o for o, v in orgs.items() if made.get(o) or (v["site"] and not v["name"] == o and o not in people)}
    kind = lambda o: "person" if o in people else "business" if o in business else "organization"
    odd = {o: why for o in sorted(keep) if o in staff and (why := implausible(kind(o), staff[o][0], org_links.get(o)))}   # flagged: the number and its year are never carried
    for o, why in odd.items():
        print(f"implausible headcount: {orgs[o]['name']} ({o}), Wikidata records {staff[o][0]:,}: {why}")
    fetched = max(v["fetched_at"] for v in saved().values())
    data = {"source": {"name": "Wikidata", "license": "CC0 1.0", "url": "https://www.wikidata.org/", "endpoint": ENDPOINT, "fetched_at": fetched,
                       "note": "Listed from Wikidata, not researched by AirStack: no facts from the product's own pages yet."},
            "types": [[c, labels[c], [ix[x] for x in sorted(parents.get(c, ())) if x in ix and reach.get(x)] or ([] if c == SOFTWARE else [ix[SOFTWARE]]), direct.get(c, 0), total[c]]
                      for c in tids],                                      # [id, name, parent types, products of exactly this type, products of it and its subtypes]
            "orgs": {o: [orgs[o]["name"], orgs[o]["site"], orgs[o]["country"], orgs[o]["founded"], made.get(o, 0), kind(o),
                         *((o not in odd and staff.get(o)) or (None, None)), org_links.get(o, 0)]
                     for o in sorted(keep)},                               # [name, website, country, founded, products listed, kind, employees, as of year, Wikipedia-family pages]
            "implausible": odd,                                            # {org: why its recorded headcount is not shown}
            "products": [[p["id"], p["name"], p["desc"], p["site"], ix[p["type"]], [d for d in p["devs"] if d in keep], p["links"], [a for a in p["aliases"] if not BLOCKED_TEXT.search(a)][:4]] for p in rows]}
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(body)
    paths.EXCLUDED.write_text(json.dumps(sorted(p["id"] for p in raw_products() if blocked(p))) + "\n")   # also withheld from published research (airstack.policy)
    print(f"directory.json: {len(data['products'])} products, {sum(1 for v in data['orgs'].values() if v[5] == 'organization')} companies, {sum(1 for v in data['orgs'].values() if v[5] == 'person')} people, {len(tids)} types, {len(body) // 1024} KB, "
          f"sha256 {hashlib.sha256(body.encode()).hexdigest()[:12]} (from {len(saved())} saved responses, read {fetched})")

if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--fetch", action="store_true"); args = a.parse_args()
    if args.fetch:
        fetch()
    build()
