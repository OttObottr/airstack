# spec: AS-252 AS-257 AS-285 AS-316 AS-317 AS-318 AS-319
"""/p/<slug>/: one page per product."""
import re
from .layout import BASE, e, foot, head
from .data import CATS, CURRENCY, DIRECTORY, LABELS, NODES, ORGS, PAIRS, TAXON, amount, app_addr, plan_ok, value
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
    paid = sorted((q for q in (Q or {}).get("plans", []) if plan_ok(q)), key=lambda q: amount(q["price"]))      # directory listings share one lane: no invented alternatives
    title = f"{p['name']}: {'pricing, plans and ' if Q else ''}{'alternatives' if peers else 'what it does'} · AirStack"
    desc = (f"{what} " if what else "") + (f"List prices from {paid[0]['price']}{' per user' if paid[0]['unit'] == 'user' else ''} / {paid[0]['period']}, quoted from its pricing page. " if paid else "") \
        + (f"Compare {p['name']} with {len(peers)} alternatives in {p['category']}, every fact quoted from each product's own pages." if peers else "Every fact quoted from its own pages, with the source.")
    url = f"{BASE}/p/{p['slug']}/"
    offers = []
    for q in (Q or {}).get("plans", []):
        m = re.search(r"([$€£¥])\s?(\d[\d,]*(?:\.\d+)?)", q["price"])
        if m: offers.append({"@type": "Offer", "name": q["plan"], "price": m.group(2).replace(",", ""), "priceCurrency": CURRENCY[m.group(1)], "url": Q["url"]})
    ld = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": p["name"], "applicationCategory": p["category"], "url": url,
          **({"description": what} if what else {}), **({"sameAs": [p["homepage"]] + ([f"https://www.wikidata.org/wiki/{p['wikidata']}"] if p.get("wikidata") else [])} if p["homepage"] else {}),
          **({"offers": offers} if offers else {}), **({"publisher": {"@type": "Organization", "name": p["vendor"]}} if p["vendor"] else {})}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "AirStack", "item": BASE + "/"}, {"@type": "ListItem", "position": 2, "name": p["category"]},
        {"@type": "ListItem", "position": 3, "name": p["name"], "item": url}]}
    src = lambda c: " ".join(f'<a href="{e(s["url"])}" rel="nofollow noopener">{e(s["host"])}</a>' for s in c.get("sources", [])[:2])
    facts = "".join(f"<tr><th>{e(l)}</th><td>{e(value(P[k]))} <small>{src(P[k])}</small></td></tr>" for k, l in LABELS if P.get(k))
    price_rows = "".join(f'<tr><td>{e(q["plan"])}</td><td><a href="{e(Q["url"])}" rel="nofollow noopener" title="{e(q["quote"])}">{e(q["price"])}</a> '
                         f'<small>{"per user " if q["unit"] == "user" else ""}{"/ month" if q["period"] == "month" else "/ year" if q["period"] == "year" else ""}</small></td></tr>' for q in (Q or {}).get("plans", []))
    alt = "".join(f'<li><a href="/p/{e(x["slug"])}/">{e(x["name"])}</a></li>' for x in peers)
    os_ = "".join(f'<li><a href="{e(r["url"])}" rel="nofollow noopener">{e(r["repo"])}</a> <small>★ {r["stars"]:,} · {e(r["license"] or "licence not stated")}</small><br><small>{e(r["description"])}</small></li>'
                  for r in (oss.get("categories", {}).get(p["lane"]) or [])[:6])
    checked = max([c.get("checked", "") for c in P.values() if isinstance(c, dict)] + [""])
    return head(title, desc, url, (ld, crumbs)) + f"""<body><main><nav><a href="/">AirStack</a> › {f'<a href="/c/{e(p["lane"])}/">{e(p["category"])}</a>' if p["lane"] in CATS else " › ".join(f'<a href="/t/{c}/">{e(NODES[c]["name"])}</a>' for c in crumbs_for(TAXON[p["id"]])) if p["id"] in TAXON else e(p['category'])}</nav>
<h1>{e(p['name'])}</h1>{f'<p class="lead">{e(what)}</p>' if what else ''}
<p><small>{e(p['category'])}{by_line(p)}{(' · <a href="' + e(p['homepage']) + '" rel="nofollow noopener">' + e(re.sub(r"^https?://(www\.)?", "", p['homepage']).split('/')[0]) + '</a>') if p['homepage'] else ''}</small></p>
<a class="cta" href="/#app={e(app_addr(p['id'], p['name']))}">Open {e(p['name'])} in AirStack</a>
{f'<h2>{e(p["name"])} pricing and plans</h2><table>{price_rows}</table><p><small>List prices as written on its pricing page, read {e(Q["checked"])}. Hover a price for the quote. Prices change: check before you buy.</small></p>' if price_rows else ''}
{f'<h2>What {e(p["name"])}’s own pages say</h2><table>{facts}</table><p><small>Each value is a quote AirStack found on the product’s own pages{", read " + e(checked) if checked else ""}. A missing field means AirStack has not found it on its pages.</small></p>' if facts else ''}
{f'<h2>{e(p["name"])} alternatives</h2><ul>{alt}</ul>' if alt else ''}
{f'<h2>Compare {e(p["name"])}</h2><ul>' + "".join(f'<li><a href="/compare/{e(sl)}/">{e(p["name"])} vs {e(o["name"])}</a></li>' for o, sl in PAIRS.get(p["id"], [])) + '</ul>' if PAIRS.get(p["id"]) else ''}
{f'<h2>Open-source alternatives to {e(p["name"])}</h2><ul>{os_}</ul><p><small>Projects tagged with {e(p["category"])} topics on GitHub, ranked by stars. A lead, not an endorsement.</small></p>' if os_ else ''}
{foot('Researched with Meta Muse. ')}
</main></body></html>
"""
