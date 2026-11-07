# spec: AS-286
"""firmographics.json: what public registers record about each company that makes a listed product, each value with its source, a
link to its record and the day it was read. Where sources disagree, every value is shown and nothing is resolved; what no source
records is left out, with the reason in "gaps".

- Wikidata (CC0): founded (P571), headquarters country (P159, then that place's country), legal parent (P749), stock listings (P414,
  with the ticker) and the LEI (P1278). Items are read one at a time from Special:EntityData, the route Wikidata's robots.txt opens
  to bots (its SPARQL endpoint and API are closed to AirStackBot). Wikidata's best rank is used and deprecated statements never
  are; a statement with an end date is reported as former. A date keeps its precision: a year is never given a day.
- GLEIF (CC0): the legal entity, its status and its direct parent, only for the LEI Wikidata records (never matched by name).
- RDAP: the day the website's domain was registered, only from registries whose terms were read and allow information use
  (Verisign: .com, .net; Public Interest Registry: .org), only for a site at its domain's root, one query a second.
- SEC EDGAR is not read: its fair-access rules ask for a contact email in the User-Agent, which only the owner can supply.

Every request goes through airstack.fetch (one honest name, robots.txt obeyed). Each source's responses are saved once per run,
gzipped, kept to the parts used (each file says which): data/wikidata-entities-raw, data/gleif-raw, data/rdap-raw. The build repeats
offline, byte for byte. No model call.

Usage: ../.venv/bin/python tools/build_firmographics.py --fetch    # read the three sources, then build
       ../.venv/bin/python tools/build_firmographics.py            # rebuild firmographics.json from what is saved"""
import argparse, gzip, json, re, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from airstack import paths

ROOT = paths.ROOT
from airstack import fetch                                                 # one honest name; robots.txt obeyed (AS-274)

OUT = paths.FIRMOGRAPHICS
WD, GL, RD = paths.DATA / "wikidata-entities-raw", paths.DATA / "gleif-raw", paths.DATA / "rdap-raw"
ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{}.json"
SIMPLE = "https://www.wikidata.org/wiki/Special:EntityData/{}.ttl?flavor=simple"   # truthy values only: a fifth of the size, for labels
PROPS = ("P17", "P154", "P159", "P414", "P571", "P749", "P1278")
GLEIF = "https://api.gleif.org/api/v1/lei-records"
RDAP = {"com": "https://rdap.verisign.com/com/v1/", "net": "https://rdap.verisign.com/net/v1/", "org": "https://rdap.publicinterestregistry.org/rdap/"}
KEPT = {"items": f"from {ENTITY}: the item's id, edit time and English label, and every statement (rank, value, qualifiers, references) "
                 f"of {', '.join(PROPS)}; the rest of each response is dropped",
        "refs": f"from {SIMPLE}: the English label and the truthy values of P17 (country), P297 (ISO code) and P1278 (LEI)"}
LEI = re.compile(r"[A-Z0-9]{20}")

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def latest(folder):
    days = sorted(folder.glob("????-??-??.json.gz")) if folder.exists() else []
    return json.loads(gzip.decompress(days[-1].read_bytes())) if days else {}

def run_file(folder, head):
    """Today's file for this source: one per run, resumed if a fetch today stopped part way."""
    f = folder / f"{now()[:10]}.json.gz"
    return f, json.loads(gzip.decompress(f.read_bytes())) if f.exists() else head

def save(f, d):
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(gzip.compress(json.dumps(d, ensure_ascii=False, sort_keys=True).encode(), mtime=0))

def entity(q):
    s, body, _ = fetch.get(ENTITY.format(q))
    rec = {"status": s, "read": now()}
    try:
        e = next(iter(json.loads(body)["entities"].values()))
    except (ValueError, KeyError, TypeError, StopIteration):
        return rec                                                         # no answer, closed, or cut off at fetch.MAX_BYTES: not read
    return rec | {"id": e.get("id"), "modified": e.get("modified"), "label": (e.get("labels", {}).get("en") or {}).get("value"),
                  "claims": {p: e["claims"][p] for p in PROPS if p in (e.get("claims") or {})}}

def ref(q):
    s, ttl, _ = fetch.get(SIMPLE.format(q))
    rec = {"status": s, "read": now()}
    if s == 200:
        m = re.search(r'rdfs:label "((?:[^"\\]|\\.)*)"@en\s*[;.,]', ttl)
        try:
            rec["label"] = json.loads(f'"{m.group(1)}"') if m else None
        except ValueError:
            rec["label"] = m.group(1)
        for p in ("P17", "P297", "P1278"):
            m = re.search(rf'wdt:{p} ((?:(?:wd:Q\d+|"[^"]*")\s*,\s*)*(?:wd:Q\d+|"[^"]*"))', ttl)
            rec[p] = [a or b for a, b in re.findall(r'wd:(Q\d+)|"([^"]*)"', m.group(1))] if m else []
    return rec

def fetch_items(ids, workers=4):
    """Every item not already read today, four at a time (Wikimedia asks bots for fewer than ten requests in flight)."""
    f, raw = run_file(WD, {"kept": KEPT, "items": {}, "refs": {}})
    todo = sorted(set(ids) - set(raw["items"]))
    with ThreadPoolExecutor(workers) as ex:
        for i in range(0, len(todo), 400):
            raw["items"].update(zip(todo[i:i + 400], ex.map(entity, todo[i:i + 400]))); save(f, raw)
            print(f"wikidata items: {min(i + 400, len(todo))}/{len(todo)}", flush=True)
    return f, raw

def fetch_wikidata(ids):
    """The companies' items, then what they point at (places, countries, exchanges, parents), then the countries of those places."""
    f, raw = fetch_items(ids)
    for _ in range(2):
        todo = sorted(referenced(raw, ids) - set(raw["refs"]) - set(raw["items"]))
        with ThreadPoolExecutor(4) as ex:
            raw["refs"].update(zip(todo, ex.map(ref, todo)))
        save(f, raw)
    return raw

def fetch_gleif(leis):
    """Each LEI's record (100 to a request), then the direct parent of each record that names one. Only LEIs Wikidata records."""
    f, raw = run_file(GL, {"kept": f"from {GLEIF}: each record's data object, as sent", "records": {}, "parents": {}})
    todo = sorted({x for x in leis if LEI.fullmatch(x)} - set(raw["records"]))
    for i in range(0, len(todo), 100):
        s, body, _ = fetch.get(f"{GLEIF}?filter[lei]={','.join(todo[i:i + 100])}&page[size]=100", headers={"Accept": "application/vnd.api+json"})
        try:
            got = {r["id"]: r for r in json.loads(body)["data"]}
        except (ValueError, KeyError, TypeError):
            got = None
        for x in todo[i:i + 100]:
            raw["records"][x] = {"status": s if got is None else 200 if x in got else 404, "read": now(), "record": (got or {}).get(x)}
        time.sleep(1)
    for x, r in sorted(raw["records"].items()):
        if x not in raw["parents"] and "lei-record" in (((r.get("record") or {}).get("relationships") or {}).get("direct-parent") or {}).get("links", {}):
            s, body, _ = fetch.get(f"{GLEIF}/{x}/direct-parent", headers={"Accept": "application/vnd.api+json"})
            try:
                raw["parents"][x] = {"status": s, "read": now(), "record": json.loads(body)["data"]}
            except (ValueError, KeyError, TypeError):
                raw["parents"][x] = {"status": s, "read": now(), "record": None}
            time.sleep(0.5)
    save(f, raw)
    return raw

def domain(site):
    """(domain, None) when the website is its own domain's root on a registry whose terms were read; else (None, why not)."""
    p = urllib.parse.urlsplit(site or "")
    host = (p.hostname or "").removeprefix("www.")
    if not site:
        return None, "no website on record"
    if p.path.strip("/") or p.query:
        return None, "the website on record is a page, not a domain's root (the domain may be someone else's)"
    if not re.fullmatch(r"[a-z0-9-]+\.[a-z]+", host):
        return None, "the website is on a subdomain"
    tld = host.rsplit(".", 1)[1]
    return (host, None) if tld in RDAP else (None, f"not read: the .{tld} registry's terms have not been reviewed")

def fetch_rdap(domains):
    f, raw = run_file(RD, {"kept": "from each registry's RDAP domain record: its events and the links of its terms-of-service notices", "domains": {}})
    for n, d in enumerate(sorted(set(domains) - set(raw["domains"]))):
        url = RDAP[d.rsplit(".", 1)[1]] + "domain/" + d
        s, body, _ = fetch.get(url, headers={"Accept": "application/rdap+json"})
        try:
            j = json.loads(body)
        except ValueError:
            j = {}
        raw["domains"][d] = {"url": url, "status": s, "read": now(), "events": j.get("events") or [],
                             "terms": sorted({l.get("href") for nt in j.get("notices") or [] for l in nt.get("links") or [] if l.get("rel") == "terms-of-service"} - {None})}
        if n % 100 == 99:
            save(f, raw); print(f"rdap: {n + 1}", flush=True)
        time.sleep(1)                                                      # registries throttle and bar high-volume querying: one a second
    save(f, raw)
    return raw

def makers():
    """The companies that make a listed product: the organizations a product page names."""
    return {o: v for o, v in json.loads(paths.DIRECTORY.read_text())["orgs"].items() if v[5] != "person" and v[4] > 0}

def statements(item, p):
    """Wikidata's best rank: the preferred statements if there are any, else the normal ones; never deprecated, never without a value."""
    st = [s for s in (item.get("claims") or {}).get(p, []) if s.get("rank") != "deprecated" and s.get("mainsnak", {}).get("snaktype") == "value"]
    return [s for s in st if s["rank"] == "preferred"] or st

def value(s):
    return s["mainsnak"]["datavalue"]["value"]

def qual(s, p):
    return [q["datavalue"]["value"] for q in (s.get("qualifiers") or {}).get(p, []) if q.get("snaktype") == "value"]

def date_of(v):
    """A Wikidata time at its own precision (9 year, 10 month, 11 day): 1986 stays 1986, never 1986-01-01. Coarser is left out."""
    m = re.match(r"\+(\d{4})-(\d\d)-(\d\d)", (v or {}).get("time", "")) if isinstance(v, dict) else None
    p = v.get("precision", 0) if m else 0
    return "-".join(m.groups()[:min(p, 11) - 8]) if p >= 9 else None

def span(s):
    """When a statement started and, if it ended, that it is former and when (an end date Wikidata does not know stays unknown)."""
    out = {"since": next(filter(None, map(date_of, qual(s, "P580"))), None)}
    if "P582" in (s.get("qualifiers") or {}):
        out |= {"former": True, "until": next(filter(None, map(date_of, qual(s, "P582"))), None)}
    return {k: v for k, v in out.items() if v is not None}

def referenced(raw, ids):
    out = set()
    for o in ids:
        it = raw["items"].get(o) or {}
        for p in ("P17", "P159", "P414", "P749"):
            for s in statements(it, p):
                out.add(value(s).get("id")); out |= {v.get("id") for v in qual(s, "P17")}
    out |= {c for r in raw["refs"].values() for c in r.get("P17", [])}
    return {x for x in out if x and re.fullmatch(r"Q\d+", x)}

def dedupe(rows, key):
    seen, out = set(), []
    for r in rows:
        if key(r) not in seen:
            seen.add(key(r)); out.append(r)
    return out

def org_record(o, site, wd, gl, rd):
    """One company's records and the gaps between them. Every entry: its value, source, a link to the record, and the day it was read."""
    items, refs = wd.get("items", {}), wd.get("refs", {})
    it = items.get(o) or {}
    label = lambda q: (items.get(q) or {}).get("label") or (refs.get(q) or {}).get("label")
    iso = lambda q: next(iter((refs.get(q) or {}).get("P297") or []), None)
    lei_of = lambda q: next(iter([value(s) for s in statements(items.get(q) or {}, "P1278")] or (refs.get(q) or {}).get("P1278") or []), None)
    day, wurl = (it.get("read") or "")[:10], lambda p: f"https://www.wikidata.org/wiki/{o}#{p}"
    wd_ = lambda p, **v: {**v, "source": "Wikidata", "url": wurl(p), "read": day}
    rec, gaps = {}, {}
    if "claims" not in it:
        gaps["wikidata"] = "the Wikidata item was not read" + (f" (status {it['status']})" if it.get("status") else "")
    rec["founded"] = dedupe([wd_("P571", value=d) for s in statements(it, "P571") if (d := date_of(value(s)))], lambda r: r["value"])
    hq = []
    for s in statements(it, "P159"):
        if "P582" in (s.get("qualifiers") or {}):
            continue                                                       # a former headquarters is not where the company is now
        place = value(s).get("id")
        for c in ([v.get("id") for v in qual(s, "P17")] or ([place] if iso(place) else (refs.get(place) or {}).get("P17", [])))[:1]:
            if label(c):
                hq.append(wd_("P159", value=label(c), code=iso(c), place=label(place) if place != c else None))
    leis = [x for x in (value(s) for s in statements(it, "P1278")) if isinstance(x, str) and LEI.fullmatch(x)]
    parents = [wd_("P749", value=label(q), id=q, lei=lei_of(q), **span(s)) for s in statements(it, "P749") if label(q := value(s).get("id"))]
    rec["listed"] = [wd_("P414", exchange=label(x), id=x, ticker=next(iter(qual(s, "P249")), None), **span(s))
                     for s in statements(it, "P414") if label(x := value(s).get("id"))]
    rec["legal_entity"] = []
    country = {iso(q): label(q) for q in sorted(refs) if iso(q) and label(q)} if leis else {}   # GLEIF gives ISO codes: name them as Wikidata does
    for x in leis:
        r = (gl.get("records") or {}).get(x) or {}
        g = r.get("record")
        if not g:
            gaps["legal_entity"] = f"GLEIF has no record for LEI {x}" if r.get("status") == 404 else f"LEI {x} not read from GLEIF yet"
            continue
        e, gd, gurl = g["attributes"]["entity"], r["read"][:10], f"https://search.gleif.org/#/record/{x}"
        rec["legal_entity"].append({"value": e["legalName"]["name"], "lei": x, "status": e.get("status"), "registration": g["attributes"]["registration"].get("status"),
                                    "jurisdiction": e.get("jurisdiction"), "source": "GLEIF", "url": gurl, "read": gd})
        a = e.get("headquartersAddress") or {}
        if a.get("country"):
            hq.append({"value": country.get(a["country"], a["country"]), "code": a["country"], "place": a.get("city"), "source": "GLEIF", "url": gurl, "read": gd})
        p = ((gl.get("parents") or {}).get(x) or {}).get("record")
        if p:
            parents.append({"value": p["attributes"]["entity"]["legalName"]["name"], "lei": p["id"], "source": "GLEIF", "url": gurl, "read": gd})
    if not leis and "claims" in it:
        gaps["legal_entity"] = "no LEI on Wikidata"
    d, why = domain(site)
    r = (rd.get("domains") or {}).get(d) if d else None
    reg = next((e["eventDate"][:10] for e in (r or {}).get("events", []) if e.get("eventAction") == "registration" and e.get("eventDate")), None)
    if not reg:
        gaps["domain_registered"] = why or ("not read from the registry yet" if not r else f"the registry's record gives no registration date (status {r['status']})")
    rec = {"founded": rec["founded"], "hq_country": dedupe(hq, lambda r: (r["source"], r["code"] or r["value"])), "parent": parents, "listed": rec["listed"],
           "legal_entity": rec["legal_entity"],
           "domain_registered": [{"value": reg, "domain": d, "source": "RDAP", "url": r["url"], "read": r["read"][:10]}] if reg else []}   # the registry's terms: source.rdap
    wd_parents = {x["lei"] for x in parents if x["source"] == "Wikidata" and not x.get("former") and x.get("lei")}
    gl_parents = {x["lei"] for x in parents if x["source"] == "GLEIF"}
    disagree = [k for k, differ in (("founded", len({x["value"][:4] for x in rec["founded"]}) > 1),
                                    ("hq_country", len({x["code"] or x["value"] for x in rec["hq_country"]}) > 1),
                                    ("parent", bool(wd_parents and gl_parents and not wd_parents & gl_parents))) if differ]
    rec = {k: [{f: v for f, v in e.items() if v is not None} for e in rows] for k, rows in rec.items() if rows}
    return rec | ({"disagree": disagree} if disagree else {}) | ({"gaps": gaps} if gaps else {})

def build():
    wd, gl, rd = latest(WD), latest(GL), latest(RD)
    orgs = makers()
    out, empty = {}, 0
    for o, row in sorted(orgs.items()):
        r = org_record(o, row[1], wd, gl, rd)
        if set(r) - {"gaps"}:
            out[o] = r
        else:
            empty += 1
    read = lambda raw, *keys: max((v.get("read") or "" for k in keys for v in (raw.get(k) or {}).values()), default="")[:10] or None
    terms = {f".{tld}": {"server": base, "terms": sorted({t for v in (rd.get("domains") or {}).values() if v["url"].startswith(base) for t in v["terms"]})}
             for tld, base in RDAP.items()}
    data = {"source": {
        "scope": f"the {len(orgs)} companies that make a product listed in directory.json; {len(out)} have at least one record",
        "rules": "Records, not estimates: each value names its source, links to its record and gives the day it was read. Where sources disagree all values are "
                 "shown and listed under disagree; nothing is resolved. What no source records is absent, with the reason under gaps.",
        "wikidata": {"name": "Wikidata", "license": "CC0 1.0", "url": "https://www.wikidata.org/", "read": read(wd, "items", "refs"),
                     "how": "each item from Special:EntityData, which Wikidata's robots.txt opens to bots; best-rank statements, deprecated ones never; an end date marks a statement former"},
        "gleif": {"name": "GLEIF LEI records", "license": "CC0 1.0", "terms": "https://www.gleif.org/en/meta/lei-data-terms-of-use", "url": GLEIF, "read": read(gl, "records", "parents"),
                  "how": "only the LEI Wikidata records for the company, never a match by name; AirStack is not affiliated with GLEIF"},
        "rdap": {"name": "RDAP domain registration data", "registries": terms, "read": read(rd, "domains"),
                 "how": "the creation date of the domain's current registration, not the company's age; only registries whose terms were read and allow information use, "
                        "one query per domain per run, a second apart"},
        "sec_edgar": "not read: SEC's fair-access rules ask for a contact email in the User-Agent, which only the owner can supply"},
        "orgs": out}
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(body)
    count = lambda k: sum(1 for r in out.values() if k in r)
    print(f"firmographics.json: {len(out)} of {len(orgs)} companies with records ({empty} with none); founded {count('founded')}, headquarters {count('hq_country')}, "
          f"parent {count('parent')}, listed {count('listed')}, legal entity {count('legal_entity')}, domain {count('domain_registered')}, "
          f"sources disagree on {count('disagree')}; {len(body) // 1024} KB")

def main():
    a = argparse.ArgumentParser(); a.add_argument("--fetch", action="store_true"); args = a.parse_args()
    if args.fetch:
        orgs = makers()
        wd = fetch_wikidata(sorted(orgs))
        fetch_gleif(sorted({value(s) for o in orgs for s in statements(wd["items"].get(o) or {}, "P1278") if isinstance(value(s), str)}))
        fetch_rdap(sorted({d for v in orgs.values() if (d := domain(v[1])[0])}))
    build()

if __name__ == "__main__":
    sys.exit(main())
