"""/t/: the software taxonomy as browsable pages."""
import shutil
from airstack import paths
from .layout import BASE, breadcrumbs, e, foot, head, trim
from .data import DIRECTORY, NODES, TAXON, app_addr, kids_members
from airstack.files import read_json, write_json

MAP_TOP = 36                                                                            # products drawn per category on the Markets map

def crumbs_for(nid):
    out = []
    while nid:
        out.append(nid); nid = NODES[nid]["parent"]
    return out[::-1]

def tax_page(nid, kids, members, direct, all_, names, descs, researched, total, placed):
    """A page per taxonomy node: its definition, its subcategories and the products placed in it (researched ones first)."""
    n = NODES[nid]; url = f"{BASE}/t/{nid}/"; path = crumbs_for(nid)
    rows = sorted(direct, key=lambda pid: (0 if pid in researched else 1, -len(descs.get(pid) or "") // 40, names[pid].lower()))
    link = lambda pid: f'<a href="/p/{all_[pid]["slug"]}/">{e(names[pid])}</a>' if pid in all_ and all_[pid].get("page") else f'<a href="/#app={e(app_addr(pid, names[pid]))}">{e(names[pid])}</a>'
    body = "".join(f'<tr><td>{link(pid)}</td><td>{e(trim(descs[pid])) if descs.get(pid) else "<small>Not observed</small>"}</td></tr>' for pid in rows)
    sub = "".join(f'<li><a href="/t/{k}/">{e(NODES[k]["name"])}</a> <small>{len(kids_members[k]):,}</small></li>' for k in kids.get(nid, []) if kids_members[k])
    nav, crumb = breadcrumbs([("AirStack", "/"), ("Software types", "/t/")] + [(NODES[c]["name"], f"/t/{c}/") for c in path[:-1]] + [(n["name"], None)])
    desc = f'{n["definition"]} {len(members):,} listed products in this part of the taxonomy, {len(members & researched):,} read from their own pages.'
    schema_rows = [pid for pid in rows if pid in all_ and all_[pid].get("page")]
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": n["name"], "url": url, "description": desc[:300],
          **({"mainEntity": {"@type": "ItemList", "numberOfItems": len(schema_rows), "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": names[pid],
                         "url": f"{BASE}/p/{all_[pid]['slug']}/"} for i, pid in enumerate(schema_rows)]}} if schema_rows else {})}
    title = f"{n['name']} software: what is listed, and what it says it does · AirStack"
    return head(title, desc, url, (ld, crumb)) + f"""<body><main>{nav}
<h1>{e(n['name'])}</h1><p class="lead">{e(n['definition'])}</p>
{f'<p><small>Includes: {e(n["includes"])}</small></p>' if n.get('includes') else ''}
{f'<h2>Subcategories</h2><ul>{sub}</ul>' if sub else ''}
{f'<h2>{len(rows):,} products directly in this type</h2><table><tr><th>Product</th><th>What it says it does</th></tr>{body}</table>' if rows else ''}
<p><small>This type and its subcategories contain {len(members):,} listed products; {len(members & researched):,} are read from their own pages. A product appears where AirStack's category data places it; {total - placed:,} of {total:,} listed products carry no category yet.</small></p>
{foot()}
</main></body></html>
"""

def taxonomy_pages(all_):
    """/t/ and a page per node, with a hub that states how much of the list is not yet placed."""
    tp, ip = paths.TAXONOMY, paths.TAXONOMY_INDEX
    if not (tp.exists() and ip.exists()):
        return []
    NODES.clear(); NODES.update({x["id"]: x for x in read_json(tp)["nodes"]}); idx = read_json(ip)
    names = {pid: p["name"] for pid, p in all_.items()} | {r[0]: r[1] for r in DIRECTORY["products"]}
    descs = {r[0]: r[2] for r in DIRECTORY["products"]} | {pid: ((p["profile"] or {}).get("what_it_does") or {}).get("value") or p.get("description") for pid, p in all_.items()}
    researched = {pid for pid, p in all_.items() if p["profile"]}
    kids = {}
    for nid, x in NODES.items(): kids.setdefault(x["parent"], []).append(nid)
    direct = {}
    for pid, placed in idx["products"].items():
        if pid in names and placed: direct.setdefault(placed[0][0], set()).add(pid); TAXON[pid] = placed[0][0]
    kids_members.clear()
    def members(nid):
        if nid not in kids_members:
            kids_members[nid] = set(direct.get(nid, set())).union(*(members(k) for k in kids.get(nid, [])))
        return kids_members[nid]
    for nid in NODES: members(nid)
    total, placed = len(names), len({pid for s in direct.values() for pid in s})
    out, urls = paths.PAGE_DIRS["t"], []; shutil.rmtree(out, ignore_errors=True); out.mkdir()
    for nid in NODES:
        if kids_members[nid]:
            d = out / nid; d.mkdir(); d.joinpath("index.html").write_text(tax_page(nid, kids, kids_members[nid], direct.get(nid, set()), all_, names, descs, researched, total, placed))
            urls.append(f"{BASE}/t/{nid}/")
    docs = {r[0]: r[6] for r in DIRECTORY["products"]}                         # how widely each is documented: Wikidata's count of Wikipedia and sister-site pages
    write_json(out / "map.json", {"total": total, "placed": placed, "nodes": {nid: [NODES[nid]["name"], NODES[nid]["parent"], len(kids_members[nid]), len(kids_members[nid] & researched),
        [[pid, names[pid], docs[pid]] for pid in sorted((x for x in kids_members[nid] if docs.get(x)), key=lambda x: (-docs[x], names[x].lower()))[:MAP_TOP]]] for nid in NODES if kids_members[nid]}})                           # the app's Markets picker reads this
    doms = "".join(f'<li><a href="/t/{d}/">{e(NODES[d]["name"])}</a> <small>{len(kids_members[d]):,} listed · {len(kids_members[d] & researched):,} read</small><br><small>{e(NODES[d]["definition"])}</small></li>' for d in sorted(kids[None], key=lambda d: -len(kids_members[d])) if kids_members[d])
    desc = f"Browse {placed:,} software products by what they do across {len([d for d in kids[None] if kids_members[d]])} top-level areas, each with its definition, subcategories and products."
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Software types", "url": f"{BASE}/t/", "description": desc}
    nav, crumb = breadcrumbs((("AirStack", "/"), ("Software types", None)))
    (out / "index.html").write_text(head("Software types: every category, with its products · AirStack", desc, f"{BASE}/t/", (ld, crumb), og_title="Software types · AirStack") + f"""<body><main>{nav}
<h1>Software types</h1><p class="lead">{e(desc)}</p>
<ul>{doms}</ul>
<p><small>{placed:,} of {total:,} listed products are placed in a category. The other {total - placed:,} are named only generically (for example “application software” or “program”) and carry no category yet; AirStack does not guess.</small></p>
{foot()}
</main></body></html>
""")
    return urls + [f"{BASE}/t/"]
