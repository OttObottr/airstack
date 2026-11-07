# spec: AS-252 AS-257 AS-285 AS-316 AS-317 AS-318 AS-319
"""/o/ and /o/in/<country>/: the makers leaderboard and country lists, and o/makers.json for the app's Makers view."""
import json, re
from airstack import paths
from .layout import BASE, e, foot, head, slug
from .data import DIRECTORY, ORGS, PAGES, site

MIN_COUNTRY = PAGES["min_country"]                                                      # makers a country needs for its own page

COUNTRY_PAGES = set()                                                            # the countries that have one, set by maker_lists() before any table is written

def maker_table(rows, made, bad, rank=True):
    nr = "<small>Not recorded</small>"
    size = lambda q, r: "<small>Out of line with its documentation, not shown</small>" if q in bad else f'{r[6]:,} <small>({e(r[7])})</small>' if r[6] and r[7] else nr
    country = lambda r: (f'<a href="/o/in/{slug(r[2])}/">{e(r[2])}</a>' if r[2] in COUNTRY_PAGES else e(r[2])) if r[2] else nr
    return ("<table><tr><th>#</th><th>Maker</th><th>Country</th><th>Founded</th><th>Employees, as Wikidata records it</th><th>Products listed</th></tr>"
            + "".join(f'<tr><td>{i if rank else ""}</td><td><a href="/o/{ORGS[q]}/">{e(r[0])}</a></td><td>{country(r)}</td><td>{e(r[3]) if r[3] else nr}</td><td>{size(q, r)}</td><td>{len(made[q])}</td></tr>'
                      for i, (q, r) in enumerate(rows, 1)) + "</table>")

def list_page(url, title, h1, lead, body, items):
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": h1, "url": url, "description": lead[:300],
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{BASE}/o/{ORGS[q]}/", "name": r[0]} for i, (q, r) in enumerate(items)]}}
    crumb = "Software makers" if url == f"{BASE}/o/" else '<a href="/o/">Software makers</a>'
    return head(title, lead, url, (ld,)) + f"""<body><main><nav><a href="/">AirStack</a> › {crumb}</nav>
<h1>{e(h1)}</h1><p class="lead">{e(lead)}</p>
{body}
<p><small>A headcount is shown with the year Wikidata gives for it; “Not recorded” means Wikidata has none.</small></p>
{foot('Organization records from Wikidata (CC0). ')}
</main></body></html>
"""

def maker_lists(keep, made):
    """The makers leaderboard as pages anyone can share and cite: /o/ (largest by headcount, most products listed, every country) and /o/in/<country>/."""
    bad = set(DIRECTORY.get("implausible", {}))
    products_too = {r[0] for r in DIRECTORY["products"]}                       # Facebook the network is a product, not a second Meta
    PUBLIC = re.compile(PAGES["not_a_business_pattern"], re.I)
    seen = set()
    def ranked(q, r):
        if r[5] != "business" or q in bad or q in products_too or PUBLIC.search(r[0]) or not (r[6] and r[7] and str(r[7]) >= "2015"):
            return False
        h = site(r[1]) if r[1] else q
        if h in seen: return False
        seen.add(h); return True
    size = lambda kv: (-(kv[1][6] or 0) if kv[0] not in bad and kv[1][7] else 1, -len(made[kv[0]]), kv[1][0].lower())
    by_size = sorted(keep.items(), key=size)
    by_count = sorted(keep.items(), key=lambda kv: (-len(made[kv[0]]), kv[1][0].lower()))
    countries = {}
    for q, r in keep.items():
        if r[2]: countries.setdefault(r[2], []).append((q, r))
    COUNTRY_PAGES.update(c for c, v in countries.items() if len(v) >= MIN_COUNTRY)
    urls, out = [], paths.PAGE_DIRS["o"]
    idx = "".join(f'<li>{f"<a href=\"/o/in/{slug(c)}/\">{e(c)}</a>" if len(v) >= MIN_COUNTRY else e(c)} <small>{len(v)}</small></li>' for c, v in sorted(countries.items(), key=lambda kv: (-len(kv[1]), kv[0])))
    top = [kv for kv in by_size if ranked(*kv)][:100]                      # businesses with a headcount dated 2015 or later, one per website
    body = f"<h2>Largest businesses by headcount</h2>{maker_table(top, made, bad)}<h2>Most products listed</h2>{maker_table(by_count[:50], made, bad)}<h2>By country</h2><ul>{idx}</ul>"
    (out / "index.html").write_text(list_page(f"{BASE}/o/", "Software makers: the largest, by headcount and products · AirStack", "Software makers",
        f"{len(keep):,} organizations that make software listed on AirStack, in {len(countries)} countries, ranked by headcount as Wikidata records it and by products listed.", body, top))
    urls.append((f"{BASE}/o/", "2026-11-05"))
    seen.clear(); order = {q: i for i, (q, r) in enumerate(kv for kv in by_size if ranked(*kv))}          # the same ranking the hub shows, for the app's Makers view
    rows = sorted(keep.items(), key=lambda kv: (order.get(kv[0], 10**6), kv[1][0].lower()))
    (out / "makers.json").write_text(json.dumps({"countries": {c: len(v) for c, v in countries.items()}, "ranked": len(order), "rows": [
        [ORGS[q], r[0], r[2] or "", str(r[3] or "")[:4], r[6] if q not in bad and r[7] else None, r[7] if q not in bad and r[7] else None,
         len(made[q]), 1 if q in order else 0, "business" if r[5] == "business" else "organization", 1 if len(countries.get(r[2], [])) >= MIN_COUNTRY else 0] for q, r in rows]},
        ensure_ascii=False, separators=(",", ":")))
    for c, v in countries.items():
        if len(v) < MIN_COUNTRY:
            continue                                                         # two makers are not a list worth a page; the hub names them without a link
        seen.clear(); first = [kv for kv in sorted(v, key=size) if ranked(*kv)]; ids = {q for q, _ in first}
        rest = sorted((kv for kv in v if kv[0] not in ids), key=lambda kv: kv[1][0].lower()); rows = first + rest
        body = (f"<h2>Largest businesses by headcount</h2>{maker_table(first, made, bad)}" if first else "") + (f"<h2>Every other maker, A to Z</h2>{maker_table(rest, made, bad, rank=False)}" if rest else "")
        d = out / "in" / slug(c); d.mkdir(parents=True, exist_ok=True)
        d.joinpath("index.html").write_text(list_page(f"{BASE}/o/in/{slug(c)}/", f"Software makers in {c} · AirStack", f"Software makers in {c}",
            f"{len(v):,} organizations in {c} that make software listed on AirStack: businesses ranked by headcount as Wikidata dates it (2015 or later), then every other maker A to Z.", body, rows))
        urls.append((f"{BASE}/o/in/{slug(c)}/", "2026-11-05"))
    return urls
