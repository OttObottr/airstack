# spec: AS-285
"""The software taxonomy, browsable like a department store: departments, their categories (data/taxonomy.json, hand-curated) and where
every listed product sits in them (taxonomy-index.json). Offline: no network, no model call, no cost.

Where a product is placed, in this order:
  catalog and registry products: one by one where data/taxonomy-crosswalk.json places them ("products"), else by their category or lane;
  directory products (Wikidata): by their Wikidata type ("types"). A type that is not listed takes the nearest listed type above it. A generic
    type (free software, mobile app, website) says nothing about the job, so the product stays unplaced: never guessed;
  researched directory products left unplaced that way: by Muse Spark from the product's own one-line description, only after that stage
    ran (--place --live) and code found the quote it gives in the description (data/taxonomy-placements.json). Muse may abstain.

Usage:  ../.venv/bin/python tools/build_taxonomy.py                           # rebuild taxonomy-index.json, byte for byte: $0
        ../.venv/bin/python tools/build_taxonomy.py --place                   # the Muse stage replayed from the memo only: $0
        ../.venv/bin/python tools/build_taxonomy.py --place --live --cap 2 --limit 50   # paid: each call is reserved in the account ledger first
--cap is this run's day and lifetime cap (default 0: nothing is paid for); the account-wide ledger cap applies as well."""
import argparse, functools, gzip, json, re
from airstack.corpus import norm
from airstack.files import atomic_write_text
from airstack import paths

ROOT = paths.ROOT
TAXONOMY, CROSSWALK, OUT = paths.TAXONOMY, paths.TAXONOMY_CROSSWALK, paths.TAXONOMY_INDEX
PLACEMENTS = paths.DATA / "taxonomy-placements.json"
TOP = 24
key = lambda n: re.sub(r"[^a-z0-9]", "", (n or "").lower())

def read(p):
    return json.loads(p.read_text())

def tree(tax):
    """Each node's parent, its chain of ancestors, and its department (the node at the top of the chain)."""
    parent = {n["id"]: n["parent"] for n in tax["nodes"]}
    anc = {}
    for n in parent:
        chain, x = [], parent[n]
        while x:
            chain.append(x); x = parent[x]
        anc[n] = chain
    return parent, anc, {n: (anc[n][-1] if anc[n] else n) for n in parent}

def type_node(t, types, xw, anc):
    """Where a Wikidata type (an index into directory.json's types) places its products: (node, the listed type that decided, candidates).
    A listed type decides for itself. An unlisted one takes the nearest listed types above it, level by level; generic and excluded
    types end the walk. When the nearest ones point to different branches, the products stay unplaced as "ambiguous"."""
    e = xw.get(types[t][0])
    if e:
        return (e[1], types[t][0], None) if e[1] else (None, e[2], None)
    seen, level = {t}, list(types[t][2])
    while level:
        found, nxt = {}, []
        for p in sorted(set(level) - seen):
            seen.add(p)
            e = xw.get(types[p][0])
            if e and e[1]:
                found.setdefault(e[1], types[p][0])
            elif not e:
                nxt += types[p][2]
        if found:
            best = sorted(n for n in found if not any(n in anc[m] for m in found if m != n))   # a department and one of its categories: the category
            return (best[0], found[best[0]], None) if len(best) == 1 else (None, "ambiguous", best)
        level = nxt
    return None, "unmapped", None

@functools.cache
def raw_links():
    """Wikipedia-family pages for catalog and registry products, which the directory leaves to them: Wikidata's record (in the saved
    product responses) with the same name and the same registered domain. Anything less certain stays unknown (None), never zero."""
    import build_directory as bd
    dom = lambda u: ".".join(bd.host(u).split(".")[-2:])
    best = {}
    for f in sorted(bd.RAW.glob("products-*.json.gz")):
        for b in json.loads(gzip.decompress(f.read_bytes()))["results"]:
            name, site = bd.q(b, "name"), bd.q(b, "site")
            if name and site:
                k = (key(name), dom(site))
                best[k] = max(best.get(k, 0), int(bd.q(b, "links") or 0))
    return lambda name, url: best.get((key(name), dom(url))) if url else None

def build(placements=None):
    tax, xw, D = read(TAXONOMY), read(CROSSWALK), read(paths.DIRECTORY)
    catalog, universe, P = read(paths.CATALOG), read(paths.UNIVERSE), read(paths.PROFILES)
    parent, anc, dept = tree(tax)
    placements = placements if placements is not None else (read(PLACEMENTS)["placed"] if PLACEMENTS.exists() else {})
    links_of = raw_links()
    placed, unplaced, ambiguous, links, names = {}, {"generic": [], "unmapped": [], "ambiguous": [], "excluded": [], "collection": []}, {}, {}, {}
    def curated(pid):
        v = xw["products"].get(pid)
        return None if v is None else [v] if isinstance(v, str) else v["nodes"]
    for e in catalog:
        names[e["id"]], links[e["id"]] = e["name"], links_of(e["name"], e.get("homepage"))
        nodes, via = curated(e["id"]), "curated"
        if nodes is None:
            nodes, via = ([xw["catalog"][e["category"]]["node"]] if xw["catalog"][e["category"]]["node"] else None), "category"
        if nodes:
            placed[e["id"]] = [[n, via] for n in nodes]
        else:
            unplaced["collection"].append(e["id"])
    for e in universe:
        names[e["id"]], links[e["id"]] = e["name"], links_of(e["name"], e.get("homepage"))
        nodes = curated(e["id"])
        placed[e["id"]] = [[n, "curated"] for n in nodes] if nodes else [[xw["lanes"][e["lane"]], "lane"]]
    memo = {}
    for p in D["products"]:
        names[p[0]], links[p[0]] = p[1], p[6]
        if p[4] not in memo:
            memo[p[4]] = type_node(p[4], D["types"], xw["types"], anc)
        node, how, cands = memo[p[4]]
        m = placements.get(p[0]) if how in ("generic", "unmapped") else None   # Muse places only what the types could not
        if node:
            placed[p[0]] = [[node, how]]
        elif m and m["node"] in parent and parent[m["node"]]:
            placed[p[0]] = [[m["node"], "muse"]]
        else:
            unplaced[how].append(p[0])
            if cands:
                ambiguous[p[0]] = cands
    members = {n: set() for n in parent}                                   # a node holds what is placed on it or anywhere below it
    for pid, nodes in placed.items():
        for n, _ in nodes:
            for x in [n] + anc[n]:
                members[x].add(pid)
    rank = lambda pid: (links[pid] is None, -(links[pid] or 0), key(names[pid]), pid)
    in_dir = {p[0] for p in D["products"]}
    def share(ids):
        ids = set(ids); n = len(ids & set(placed))
        return {"listed": len(ids), "placed": n, "unplaced": len(ids) - n, "share_placed": round(n / len(ids), 4) if ids else None}
    return {"source": {"taxonomy": "data/taxonomy.json and data/taxonomy-crosswalk.json, hand-curated by AirStack (CC BY 4.0)",
                       "listed_from": f"directory.json ({D['source']['name']}, {D['source']['license']}, read {D['source']['fetched_at'][:10]}), data/catalog.json, data/universe.json",
                       "researched": "a product is researched when profiles.json holds facts from its own pages",
                       "top": f"up to {TOP} products per node, ordered by Wikipedia-family pages (how widely a product is documented, not how widely it is used); unknown last",
                       "muse": (f"{sum(v[0][1] == 'muse' for v in placed.values())} placed by Muse Spark from the product's own one-line description, the quote checked by code"
                                if any(v[0][1] == "muse" for v in placed.values()) else "no product is placed by a model")},
            "summary": {"products": len(names), "placed": len(placed), "in_a_category": sum(any(parent[n] for n, _ in v) for v in placed.values()),
                        "department_only": sum(not any(parent[n] for n, _ in v) for v in placed.values()), "by_muse": sum(v[0][1] == "muse" for v in placed.values()),
                        "unplaced": {k: len(v) for k, v in unplaced.items()},
                        "directory": share(in_dir), "catalog": share(e["id"] for e in catalog), "registry": share(e["id"] for e in universe)},
            "nodes": {n["id"]: {"listed": len(members[n["id"]]), "researched": len(members[n["id"]] & set(P)), "top": sorted(members[n["id"]], key=rank)[:TOP]}
                      for n in tax["nodes"]},
            "products": dict(sorted(placed.items())), "unplaced": {k: sorted(v) for k, v in unplaced.items()}, "ambiguous": dict(sorted(ambiguous.items()))}

def write(idx):
    body = json.dumps(idx, ensure_ascii=False, separators=(",", ":"))
    atomic_write_text(OUT, body)
    s = idx["summary"]
    print(f"taxonomy-index.json: {s['placed']:,} of {s['products']:,} products placed ({s['in_a_category']:,} in a category); directory "
          f"{s['directory']['placed']:,} of {s['directory']['listed']:,} placed ({s['directory']['share_placed']:.1%}); unplaced {s['unplaced']}; {len(body) // 1024} KB")

# ---- the Muse placement stage: designed and tested with FakeSpark; paid only with --live and a cap the owner sets ----
def menu(tax):
    """The categories Muse may choose from, each as [id, "Department > Category"]. Departments are not offered: a placement names a category."""
    by = {n["id"]: n for n in tax["nodes"]}
    path = lambda n: ([*path(by[n]["parent"])] if by[n]["parent"] else []) + [by[n]["name"]]
    return [[n["id"], " > ".join(path(n["id"]))] for n in tax["nodes"] if n["parent"]]

def candidates(idx, D, P):
    """Researched directory products whose Wikidata type said nothing about the job, with the one-line description from their own pages.
    A description from a page closed to AirStack since (robots.txt, terms) is not sent."""
    from airstack.fetch import published
    want, out = set(idx["unplaced"]["generic"]) | set(idx["unplaced"]["unmapped"]), []
    for p in D["products"]:
        w = (P.get(p[0]) or {}).get("what_it_does") or {}
        src = (w.get("sources") or [{}])[0].get("url")
        if p[0] in want and isinstance(w.get("value"), str) and w["value"].strip() and src and published(src):
            out.append({"id": p[0], "name": p[1], "description": w["value"].strip(), "url": src})
    return out

def payload(item, choices):
    return {"product": item["name"], "description": item["description"], "categories": choices}

def verdict(node, quote, description, ids):
    """Why a placement may not be kept (None = keep it)."""
    if node not in ids:
        return "not a category in the list"
    if len(quote.split()) < 2:
        return "quote too short"
    if norm(quote) not in norm(description):
        return "quote not in the product's description"
    return None

def place(spark, corpus, items, choices, *, live, limit=None):
    """One call per product, memoised: a product already placed (or abstained on) replays for free. Without --live only the memo is read and
    Muse is never called. --limit caps new paid calls only, so a short run never drops what earlier runs paid for."""
    from airstack.budget import BudgetExceeded
    from airstack.config import MODEL
    from airstack.spark import memo_key
    model = getattr(spark.inner, "model_for", lambda r: MODEL)("place")
    ids, rep = {c[0] for c in choices}, {"placed": {}, "abstained": [], "rejected": {}, "not_run": 0, "calls": 0, "replayed": 0, "stopped": None}
    for it in items:
        pl = payload(it, choices)
        paid = corpus.get(memo_key("place", pl, model)) is None
        if paid and (not live or rep["stopped"] or (limit is not None and rep["calls"] >= limit)):
            rep["not_run"] += 1; continue
        try:
            res = spark.call("place", pl, tool=it["id"])
        except BudgetExceeded as ex:
            if ex.reason == "input_too_large":
                rep["rejected"][it["id"]] = "description too long to send"; continue
            rep["stopped"] = f"{ex.reason}: stopped before {it['id']}"; rep["not_run"] += 1; continue
        except Exception as ex:
            rep["rejected"][it["id"]] = f"call failed: {type(ex).__name__}"; continue
        rep["calls" if paid else "replayed"] += 1
        node, quote = res.data["node"].strip(), res.data["quote"].strip()
        if not node:
            rep["abstained"].append(it["id"]); continue
        why = verdict(node, quote, it["description"], ids)
        if why:
            rep["rejected"][it["id"]] = why
        else:
            rep["placed"][it["id"]] = {"node": node, "quote": quote, "source": it["url"], "call_ref": res.call_id}
    return rep

def run_stage(idx, live, cap, limit):
    from airstack.budget import BudgetGuard
    from airstack.corpus import Corpus
    from airstack.spark import FakeSpark, GuardedSpark, PROMPT_VERSION
    from airstack.store import Store, utcnow
    store = Store(str(paths.MARKET_DB)); corpus = Corpus(store)
    if live:
        import preflight; preflight.load_env(ROOT / ".env")
        from airstack.spark import LiveSpark
        inner = LiveSpark()
    else:
        inner = FakeSpark({}, cost="0", replay_only=True)
    spark = GuardedSpark(inner, store, BudgetGuard(store, utcnow, job_cap="0.10", day_cap=cap, total_cap=cap, tool_calls=2, tool_searches=0), utcnow, memo=corpus)
    tax = read(TAXONOMY)
    rep = place(spark, corpus, candidates(idx, read(paths.DIRECTORY), read(paths.PROFILES)), menu(tax), live=live, limit=limit)
    atomic_write_text(PLACEMENTS, json.dumps({"source": {"model": getattr(inner, "model_label", "muse"), "prompt": PROMPT_VERSION["place"],
                                                          "note": "Muse Spark placed each product from its own one-line description; code kept a placement only when the quote it gave is in that description."},
                                               "placed": dict(sorted(rep["placed"].items())), "abstained": sorted(rep["abstained"]),
                                               "rejected": dict(sorted(rep["rejected"].items()))}, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: (len(v) if isinstance(v, (dict, list)) else v) for k, v in rep.items()}))

def main(argv=None):
    a = argparse.ArgumentParser(); a.add_argument("--place", action="store_true"); a.add_argument("--live", action="store_true")
    a.add_argument("--cap", default="0"); a.add_argument("--limit", type=int, help="at most this many new paid calls")
    args = a.parse_args(argv)
    idx = build()
    if args.place:
        run_stage(idx, args.live, args.cap, args.limit)
        idx = build()
    write(idx)

if __name__ == "__main__":
    main()
