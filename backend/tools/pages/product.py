"""/p/<slug>/: one page per product, plus the product directory."""
import collections
import re
from airstack import paths
from .layout import BASE, breadcrumbs, e, foot, head
from .data import CATS, DIRECTORY, LABELS, NODES, ORGS, PAIRS, TAXON, app_addr, day, fact_cell, listed
from .taxonomy import crumbs_for

def by_line(p):
    """The maker, linked to its organization page when it has one."""
    if p.get("makers"):
        names = [f'<a href="/o/{ORGS[m]}/">{e(DIRECTORY["orgs"][m][0])}</a>' if m in ORGS else e(DIRECTORY["orgs"][m][0]) for m in p["makers"]]
        return " · by " + ", ".join(names)
    return (" · by " + e(p["vendor"])) if p["vendor"] else ""

def page(p, all_, prices, oss):
    P, Q = p["profile"] or {}, prices.get(p["id"])
    what = P.get("what_it_does", {}).get("value") if P.get("what_it_does") else p.get("description")
    peers = [] if p["lane"] == "directory" else sorted((x for x in all_.values() if x["lane"] == p["lane"] and x["id"] != p["id"] and x["profile"]), key=lambda x: -x["profile"]["facts"])[:10]
    title = f"{p['name']}: {'pricing, plans and ' if Q else ''}{'alternatives' if peers else 'what it does'} · AirStack"
    desc = f"{p['name']}: " + (f"{what} " if what else "") + ("Its plans and list prices as its pricing page lists them, with the date. " if Q else "") \
        + (f"Compare {p['name']} with {len(peers)} alternatives in {p['category']}, every fact quoted from each product's own pages." if peers else "Every fact quoted from its own pages, with the source.")
    url = f"{BASE}/p/{p['slug']}/"
    ld = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": p["name"], "applicationCategory": p["category"], "url": url,
          **({"description": what} if what else {}), **({"sameAs": [p["homepage"]] + ([f"https://www.wikidata.org/wiki/{p['wikidata']}"] if p.get("wikidata") else [])} if p["homepage"] else {}),
          **({"publisher": {"@type": "Organization", "name": p["vendor"]}} if p["vendor"] else {})}
    trail = [("AirStack", "/"), ("Products", "/p/")]
    if p["lane"] in CATS:
        trail.append((p["category"], f'/c/{p["lane"]}/'))
    elif p["id"] in TAXON:
        trail += [("Software types", "/t/")] + [(NODES[c]["name"], f"/t/{c}/") for c in crumbs_for(TAXON[p["id"]])]
    trail.append((p["name"], None)); nav, crumbs = breadcrumbs(trail)
    facts = "".join(f"<tr><th>{e(ln)}</th><td>{fact_cell(p, k, ln, P[k])}</td></tr>" for k, ln in LABELS if P.get(k))
    price_rows = "".join(f'<tr><th>{e(q["plan"])}</th><td>{e(q["price"])} <small>{"per user " if q["unit"] == "user" else ""}{"/ month" if q["period"] == "month" else "/ year" if q["period"] == "year" else ""}'
                         f'<br>The pricing page says: <q>{e(q["quote"])}</q></small></td></tr>' for q in (Q or {}).get("plans", []))
    alt = "".join(f'<li><a href="/p/{e(x["slug"])}/">{e(x["name"])}</a></li>' for x in peers)
    os_ = "".join(f'<li><a href="{e(r["url"])}" rel="nofollow noopener">{e(r["repo"])}</a> <small>★ {r["stars"]:,} · {e(r["license"] or "licence not stated")}</small><br><small>{e(r["description"])}</small></li>'
                  for r in (oss.get("categories", {}).get(p["lane"]) or [])[:6])
    checked = max([c.get("checked", "") for c in P.values() if isinstance(c, dict)] + [""])
    return head(title, desc, url, (ld, crumbs)) + f"""<body><main>{nav}
<h1>{e(p['name'])}</h1>{f'<p class="lead">{e(what)}</p>' if what else ''}
<p><small>{e(p['category'])}{by_line(p)}{(' · <a href="' + e(p['homepage']) + '" rel="nofollow noopener">' + e(re.sub(r"^https?://(www\.)?", "", p['homepage']).split('/')[0]) + '</a>') if p['homepage'] else ''}{(' · <a href="' + e(p['trust']) + '" rel="nofollow noopener">Vendor’s trust page</a>') if p.get('trust') else ''}</small></p>
<a class="cta" href="/#app={e(app_addr(p['id'], p['name']))}">Open {e(p['name'])} in AirStack</a>
{f'<h2>{e(p["name"])} plans and list prices</h2><p><small>{listed(Q)}. Prices change: check with the vendor.</small></p><table>{price_rows}</table>' if price_rows else ''}
{f'<h2>What {e(p["name"])}’s pages say</h2><table>{facts}</table><p><small>Vendor statements, quoted and dated{", last read " + day(checked) if checked else ""}; not verified by AirStack. A missing field means AirStack has not found it on its pages.</small></p>' if facts else ''}
{f'<h2>{e(p["name"])} alternatives</h2><ul>{alt}</ul>' if alt else ''}
{f'<h2>Compare {e(p["name"])}</h2><ul>' + "".join(f'<li><a href="/compare/{e(sl)}/">{e(p["name"])} vs {e(o["name"])}</a></li>' for o, sl in PAIRS.get(p["id"], [])) + '</ul>' if PAIRS.get(p["id"]) else ''}
{f'<h2>Open-source alternatives to {e(p["name"])}</h2><ul>{os_}</ul><p><small>Projects tagged with {e(p["category"])} topics on GitHub, ranked by stars. A lead, not an endorsement.</small></p>' if os_ else ''}
{foot('Facts extracted with Muse Spark. ')}
</main></body></html>
"""


def product_directory(all_):
    """A crawlable path to every product page, split into small alphabetical pages."""
    groups = collections.defaultdict(list)
    for p in sorted((p for p in all_.values() if p.get("page")), key=lambda x: x["name"].lower()):
        first = p["name"][:1].lower(); groups[first if first.isalpha() else "0-9" if first.isdigit() else "other"].append(p)
    out = paths.PAGE_DIRS["p"] / "by"; out.mkdir(exist_ok=True)
    urls = []
    for key, rows in sorted(groups.items()):
        url = f"{BASE}/p/by/{key}/"; d = out / key; d.mkdir(exist_ok=True)
        lead = f"{len(rows):,} software products beginning with {key.upper()}, each linked to its AirStack evidence page."
        nav, crumb = breadcrumbs((("AirStack", "/"), ("Products", "/p/"), (key.upper(), None)))
        ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": f"Software products: {key.upper()}", "url": url, "description": lead,
              "mainEntity": {"@type": "ItemList", "numberOfItems": len(rows), "itemListElement": [{"@type": "ListItem", "position": i, "name": p["name"], "url": f"{BASE}/p/{p['slug']}/"} for i, p in enumerate(rows, 1)]}}
        links = "".join(f'<li><a href="/p/{e(p["slug"])}/">{e(p["name"])}</a> <small>{e(p["category"])}</small></li>' for p in rows)
        d.joinpath("index.html").write_text(head(f"Software products beginning with {key.upper()} · AirStack", lead, url, (ld, crumb)) + f"<body><main>{nav}<h1>Software products: {e(key.upper())}</h1><p class=\"lead\">{e(lead)}</p><ul>{links}</ul>{foot()}</main></body></html>\n")
        urls.append(url)
    url = f"{BASE}/p/"; lead = f"Browse {sum(map(len, groups.values())):,} researched software products by name."
    nav, crumb = breadcrumbs((("AirStack", "/"), ("Products", None)))
    items = [(key, rows) for key, rows in sorted(groups.items())]
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Software products", "url": url, "description": lead,
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [{"@type": "ListItem", "position": i, "name": key.upper(), "url": f"{BASE}/p/by/{key}/"} for i, (key, _) in enumerate(items, 1)]}}
    links = "".join(f'<li><a href="/p/by/{e(key)}/">{e(key.upper())}</a> <small>{len(rows):,}</small></li>' for key, rows in items)
    paths.PAGE_DIRS["p"].joinpath("index.html").write_text(head("Software products A–Z · AirStack", lead, url, (ld, crumb)) + f"<body><main>{nav}<h1>Software products A–Z</h1><p class=\"lead\">{e(lead)}</p><ul>{links}</ul>{foot()}</main></body></html>\n")
    return [url] + urls
