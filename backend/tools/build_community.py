# spec: AS-264 AS-295
"""Communities and public channels, as Wikidata (CC0) records them, for every product and maker AirStack lists: subreddit, LinkedIn, X,
YouTube, GitHub, Mastodon, Instagram, Facebook, Discord, Threads, Bluesky, TikTok and blog ids; follower counts with the date each was stated;
and, for makers, the founders, chief executives and directors Wikidata names (people with an item of their own): name, role and item only, never their personal accounts.
Links and counts are Wikidata's, never scraped from the platforms. Every raw response is saved with its query and time
(data/wikidata-raw/community/, beside but apart from the directory's own files), and the build repeats offline. No model call, no cost.

Catalog products carry no Wikidata id: one is joined to the item whose official website host AND name both match it in the directory's
saved Wikidata records (data/wikidata-raw/products-*); an ambiguous match is left out.

Usage:  ../.venv/bin/python tools/build_community.py --fetch    # query Wikidata (resumes; delete data/wikidata-raw/community/ to refresh)
        ../.venv/bin/python tools/build_community.py            # rebuild community.json offline, byte for byte, from the saved responses"""
import argparse, gzip, json, re
import build_directory as directory
from airstack import paths, wikidata
from airstack.wikidata import ENDPOINT

ROOT = paths.ROOT
RAW, OUT = paths.DATA / "wikidata-raw" / "community", paths.COMMUNITY
BATCH = 200
LINKS = {"P3984": "subreddit", "P4264": "linkedin", "P2002": "x", "P2397": "youtube", "P2037": "github", "P4033": "mastodon",
         "P2003": "instagram", "P2013": "facebook", "P9345": "discord", "P11892": "threads", "P12361": "bluesky", "P7085": "tiktok",
         "P1581": "blog"}
ROLES = {"P112": "founder", "P169": "ceo", "P1037": "director"}
FOLLOWED_ON = {**{p: k for p, k in LINKS.items() if p != "P1581"}, "P6552": "x", "P11245": "youtube", "P12409": "bluesky",
               "P12546": "instagram", "P11705": "facebook"}                                # the qualifier naming the account a count is for
ID, MASTODON = r"[^/\s@]+", r"@?[^/\s@]+@[^/\s@]+\.[^/\s@]+"                              # an id or handle, never an address
PRECISION = {9: 4, 10: 7, 11: 10}                                                         # year, month, day: a date says no more than Wikidata does

def sparql(name, query):
    wikidata.sparql(RAW, name, query)

def load(prefix):
    return [b for f in sorted(RAW.glob(f"{prefix}-*.json.gz")) for b in json.loads(gzip.decompress(f.read_bytes()))["results"]]

q, qid = wikidata.q, wikidata.qid
def pid(u):
    """A Wikidata property id (P123) from its URI, or nothing: never a free string."""
    v = u.rsplit("/", 1)[-1] if u else None
    return v if v and re.fullmatch(r"P\d+", v) else None
key = lambda n: re.sub(r"[^a-z0-9]", "", n.lower())

def catalog():
    """Catalog id -> [its Wikidata item, then that item's developers]: website host and name must both match one item."""
    index = {}
    for p in directory.raw_products():
        if p["site"]:
            index.setdefault((directory.host(p["site"]), key(p["name"])), {})[p["id"]] = p["devs"]
    out = {}
    for t in json.loads(paths.CATALOG.read_text()):
        hit = index.get((directory.host(t.get("homepage")), key(t["name"])), {})
        if len(hit) == 1:
            (i, devs), = hit.items(); out[t["id"]] = [i, *sorted({d for d in devs if d}, key=lambda d: int(d[1:]))]
    return out

def listed():
    """(every listed QID, the makers among them, the catalog join): directory products and organisations, the catalog's matched items and
    their developers. A maker who is a person (Wikidata: instance of human) is not an organisation: no channels are gathered for them here."""
    d = json.loads(paths.DIRECTORY.read_text())
    humans = {qid(q(b, "o")) for b in directory.load("people-")} | {o for o, v in d["orgs"].items() if v[5] == "person"}
    cat = {c: [v[0], *[m for m in v[1:] if m not in humans]] for c, v in catalog().items()}
    makers = (set(d["orgs"]) | {m for v in cat.values() for m in v[1:]}) - humans
    return {p[0] for p in d["products"]} | makers | {v[0] for v in cat.values()}, makers, cat

def values(ids):
    if not all(re.fullmatch(r"Q\d+", i) for i in ids):
        raise ValueError("only Wikidata item ids go into a query")
    return " ".join(f"wd:{i}" for i in ids)

def links_query(ids, props):    # statements, not truthy values: an ended or deprecated handle is not current
    return f"""SELECT ?s ?prop ?v ?rank ?end ?invite WHERE {{ VALUES ?s {{ {values(ids)} }} VALUES ?prop {{ {" ".join(f"wd:{p}" for p in sorted(props))} }}
      ?prop wikibase:claim ?p ; wikibase:statementProperty ?ps . ?s ?p ?st . ?st ?ps ?v ; wikibase:rank ?rank . FILTER(?rank != wikibase:DeprecatedRank)
      OPTIONAL {{ ?st pq:P582 ?end }} OPTIONAL {{ ?st pq:P9078 ?invite }} }}"""

def batches(ids):
    ids = sorted(ids, key=lambda i: int(i[1:]))
    return [ids[i:i + BATCH] for i in range(0, len(ids), BATCH)]

def fetch():
    every, makers, _ = listed()
    for n, ids in enumerate(batches(every)):
        sparql(f"links-{n:03d}", links_query(ids, LINKS))
        sparql(f"followers-{n:03d}", f"""SELECT ?s ?st ?n ?rank ?when ?precision ?pq ?qv WHERE {{ VALUES ?s {{ {values(ids)} }}
          ?s p:P8687 ?st . ?st ps:P8687 ?n ; wikibase:rank ?rank . FILTER(?rank != wikibase:DeprecatedRank)
          OPTIONAL {{ ?st pqv:P585 ?t . ?t wikibase:timeValue ?when ; wikibase:timePrecision ?precision }}
          OPTIONAL {{ ?st ?pq ?qv FILTER(STRSTARTS(STR(?pq), "http://www.wikidata.org/prop/qualifier/P")) }} }}""")
    for n, ids in enumerate(batches(makers)):
        sparql(f"people-{n:03d}", f"""SELECT ?o ?role ?person ?rank ?end ?name WHERE {{ VALUES ?o {{ {values(ids)} }} VALUES ?role {{ {" ".join(f"wd:{p}" for p in ROLES)} }}
          ?role wikibase:claim ?p ; wikibase:statementProperty ?ps . ?o ?p ?st . ?st ?ps ?person ; wikibase:rank ?rank . FILTER(?rank != wikibase:DeprecatedRank)
          ?person wdt:P31 wd:Q5 . OPTIONAL {{ ?st pq:P582 ?end }} OPTIONAL {{ ?person rdfs:label ?name FILTER(LANG(?name) IN ("en", "mul")) }} }}""")

def best(rows):
    """Wikidata's own reading of several statements: preferred rank wins over normal."""
    top = [r for r in rows if q(r, "rank").endswith("PreferredRank")]
    return top or rows

def links(prefix, names):
    found = {}
    for b in load(prefix):
        if not q(b, "end"):                                                # a statement with an end date is not current
            found.setdefault(qid(q(b, "s")), {}).setdefault(pid(q(b, "prop")), []).append(b)
    out = {}
    for s, props in found.items():
        for p, rows in props.items():
            rows = best(rows)
            ok = [q(r, "v") for r in rows if p == "P1581" or re.fullmatch(MASTODON if p == "P4033" else ID, q(r, "v"))]
            if not ok:                                                     # a full address or a stray value where an id belongs: not an id
                continue
            v = min(ok)
            if p == "P3984": v = "r/" + v
            if p == "P4033": v = "@" + v.lstrip("@")                       # a fediverse handle, @user@server
            out.setdefault(s, {})[names[p]] = v
            invite = min((q(r, "invite") for r in rows if q(r, "invite")), default=None)
            if p == "P9345" and invite: out[s]["discord_invite"] = invite
    return {s: dict(sorted(v.items())) for s, v in out.items()}

def followers():
    """The latest count per platform, with the date Wikidata gives for it (to its stated precision); an undated one only when nothing is dated."""
    st = {}
    for b in load("followers"):
        r = st.setdefault(q(b, "st"), {"s": qid(q(b, "s")), "n": q(b, "n"), "rank": q(b, "rank"), "when": q(b, "when"), "prec": q(b, "precision"), "on": set()})
        if q(b, "pq"):
            p = q(b, "pq").rsplit("/", 1)[-1]
            if p in FOLLOWED_ON: r["on"].add(FOLLOWED_ON[p])
    out = {}
    for r in st.values():
        try: n = int(r["n"]) if float(r["n"]) == int(float(r["n"])) else None
        except (TypeError, ValueError): n = None
        if n is None or n < 0 or len(r["on"]) != 1:                         # a count must say which platform it is for
            continue
        when = r["when"] if re.match(r"\d{4}-\d\d-\d\dT", r["when"] or "") else None
        cut = PRECISION.get(int(r["prec"] or 0)) if when else None
        platform, rank = next(iter(r["on"])), (when or "", r["rank"].endswith("PreferredRank"), n)
        cur = out.setdefault(r["s"], {}).get(platform)
        if cur is None or rank > cur[0]:
            out[r["s"]][platform] = (rank, [platform, n, when[:cut] if cut else None])
    return {s: [v[1] for _, v in sorted(p.items())] for s, p in out.items()}

def people(makers):
    rows = {}
    for b in load("people"):
        o, role, person = qid(q(b, "o")), ROLES[pid(q(b, "role"))], qid(q(b, "person"))
        if o in makers and re.fullmatch(r"Q\d+", person or "") and not (role != "founder" and q(b, "end")):   # a former chief executive is not the current one
            rows.setdefault((o, role), {}).setdefault(person, []).append(b)
    out = {}
    for (o, role), ps in rows.items():
        keep = [r for rs in ps.values() for r in rs]
        keep = keep if role == "founder" else best(keep)                   # every founder stays one; of chief executives, the preferred is current
        for person in sorted({qid(q(r, "person")) for r in keep}, key=lambda i: int(i[1:])):
            names = {r["name"]["xml:lang"]: q(r, "name") for r in ps[person] if r.get("name")}
            name = names.get("en") or names.get("mul")
            if name:                                                       # a person is shown by name or not at all
                out.setdefault(o, []).append([person, name, role])            # name, role and Wikidata item only: no personal handles are published
    order = list(ROLES.values())
    return {o: sorted(v, key=lambda r: (order.index(r[2]), r[1], r[0])) for o, v in out.items()}

def build():
    every, makers, cat = listed()
    lk, fl, pp = links("links", LINKS), followers(), people(makers)
    ents = {}
    for s in sorted(every, key=lambda i: int(i[1:])):
        e = {**({"links": lk[s]} if s in lk else {}), **({"followers": fl[s]} if s in fl else {}), **({"people": pp[s]} if s in pp else {})}
        if "links" in e or "people" in e:
            ents[s] = e
    fetched = max(json.loads(gzip.decompress(f.read_bytes()))["fetched_at"] for f in RAW.glob("*.json.gz"))
    data = {"source": {"name": "Wikidata", "licence": "CC0", "url": "https://www.wikidata.org/", "endpoint": ENDPOINT, "fetched_at": fetched,
                       "note": "Links and counts as Wikidata records them, with the date each count was stated. Not scraped from the platforms; "
                               "a missing link means Wikidata has none, not that none exists."},
            "catalog": {c: v for c, v in sorted(cat.items()) if any(i in ents for i in v)},   # catalog id -> [its Wikidata item, its developers]
            "entities": ents}
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(body)
    n = lambda k: sum(1 for e in ents.values() if k in e.get("links", {}))
    print(f"community.json: {len(ents)} entities ({n('subreddit')} subreddit, {n('linkedin')} LinkedIn, {n('x')} X, "
          f"{sum(1 for e in ents.values() if 'followers' in e)} with follower counts, {sum(1 for e in ents.values() if 'people' in e)} with people), "
          f"{len(data['catalog'])} catalog products joined, {len(body) // 1024} KB (read {fetched})")

if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--fetch", action="store_true"); args = a.parse_args()
    if args.fetch:
        fetch()
    build()
