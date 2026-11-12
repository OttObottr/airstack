"""/compare/<a>-vs-<b>/: two products side by side from their own pages."""
import shutil
from airstack import paths
from .layout import BASE, breadcrumbs, e, foot, head
from .data import LABELS, PAGES, PAIRS, TAXON, fact_cell, listed
from airstack.files import read_json

SHARED = PAGES["shared_facts"]  # a pair gets a page only with at least this many facts stated on both sides

def pair_slug(a, b):
    x, y = sorted([a, b], key=lambda z: z["slug"]); return f"{x['slug']}-vs-{y['slug']}", x, y

def cell(p, k):
    P = p["profile"]
    c = P.get(k) if P else None
    if not c:
        return "<small>Not observed</small>"
    return fact_cell(p, k, dict(LABELS)[k], c, most=1)          # one quote per cell side by side; the product page has them all

def price_cell(q):
    return f"<small>{listed(q)}: {e(', '.join(x['plan'] for x in q['plans']))}.</small>" if q and q.get("plans") else "<small>Not observed</small>"

def differences(a, b):
    """What one product's own pages state and the other's don't. Nothing is ranked."""
    A, B, out = a["profile"] or {}, b["profile"] or {}, []
    for k, label in (("free_plan", "a free plan"), ("open_source", "that it is open source")):
        va, vb = (A.get(k) or {}).get("value") is True, (B.get(k) or {}).get("value") is True
        if va != vb: out.append(f"{(a if va else b)['name']}’s pages state {label}; AirStack has not found that on {(b if va else a)['name']}’s pages.")
    return out[:8]

def compare_page(a, b, prices, cat):
    slugv, a, b = pair_slug(a, b); url = f"{BASE}/compare/{slugv}/"; qa, qb = prices.get(a["id"]), prices.get(b["id"])
    rows = [("What it says it does", cell(a, "what_it_does"), cell(b, "what_it_does")), ("List prices", price_cell(qa), price_cell(qb))]
    rows += [(lab, cell(a, k), cell(b, k)) for k, lab in LABELS[1:] if (a["profile"] or {}).get(k) or (b["profile"] or {}).get(k)]
    table = "".join(f"<tr><th>{e(ln)}</th><td>{x}</td><td>{y}</td></tr>" for ln, x, y in rows)
    diff = differences(a, b)
    desc = f"{a['name']} vs {b['name']}, from each product’s own pages: " + (diff[0] if diff else "plans, platforms and integrations, side by side.")
    title = f"{a['name']} vs {b['name']}: plans, prices and features compared · AirStack.bot"
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": f"{a['name']} vs {b['name']}", "url": url, "description": desc[:300],
          "about": [{"@type": "SoftwareApplication", "name": x["name"], "url": f"{BASE}/p/{x['slug']}/", "applicationCategory": x["category"]} for x in (a, b)]}
    nav, crumb = breadcrumbs((("AirStack", "/"), ("Categories", "/c/"), (cat, f'/c/{a["lane"]}/'), (f"{a['name']} vs {b['name']}", None)))
    return slugv, head(title, desc, url, (ld, crumb)) + f"""<body><main>{nav}
<h1>{e(a['name'])} vs {e(b['name'])}</h1>
<p class="lead">What each one’s own pages say, side by side, quoted and dated. “Not observed” means AirStack has not found it on that product’s pages.</p>
<table><tr><th></th><th><a href="/p/{e(a['slug'])}/">{e(a['name'])}</a></th><th><a href="/p/{e(b['slug'])}/">{e(b['name'])}</a></th></tr>{table}</table>
{'<h2>How do ' + e(a['name']) + ' and ' + e(b['name']) + ' differ?</h2><ul>' + "".join(f"<li>{e(d)}</li>" for d in diff) + '</ul>' if diff else ''}
<p><small>Vendor statements, quoted and dated; not verified by AirStack. Check with the vendor.</small></p>
{foot()}
</main></body></html>
"""

def compare_pages(all_, prices):
    """Pairs in one category and one software type whose own pages state at least SHARED of the same facts."""
    ins = read_json(paths.INSIGHTS) if paths.INSIGHTS.exists() else {"map": {"points": []}}
    docs = {pt[0]: pt[3] for pt in ins["map"]["points"]}
    out = paths.PAGE_DIRS["compare"]; shutil.rmtree(out, ignore_errors=True); urls, named = [], []
    site = paths.read_js(paths.SITE_DATA); cats = {c["id"]: c["name"] for c in site.get("cats", [])}
    for cid, cname in cats.items():
        top = sorted((x for x in all_.values() if x["lane"] == cid and x.get("page") and x["profile"] and (x["profile"].get("facts") or 0) >= 5),
                     key=lambda x: (-docs.get(x["id"], 0), -(x["profile"].get("facts") or 0), x["name"].lower()))
        for i, a in enumerate(top):
            for b in top[i + 1:]:
                if TAXON.get(a["id"]) is None or TAXON.get(a["id"]) != TAXON.get(b["id"]) or sum(1 for k, _ in LABELS if a["profile"].get(k) and b["profile"].get(k)) < SHARED:
                    continue
                slugv, h = compare_page(a, b, prices, cname)
                d = out / slugv; d.mkdir(parents=True, exist_ok=True); d.joinpath("index.html").write_text(h)
                for x, y in ((a, b), (b, a)): PAIRS.setdefault(x["id"], []).append((y, slugv))
                urls.append(f"{BASE}/compare/{slugv}/"); named.append((slugv, f"{a['name']} vs {b['name']}"))
    return [compare_hub(out, named)] + urls

def compare_hub(out, named):
    """/compare/ with no pair opens the app's comparison; the static list stays for readers without it."""
    url, lead = f"{BASE}/compare/", "Pick 2 to 5 products and see what each one’s own pages state, side by side, with the page and the day each fact was found."
    nav, crumb = breadcrumbs((("AirStack", "/"), ("Compare software", None)))
    pairs = "".join(f'<li><a href="/compare/{e(s)}/">{e(label)}</a></li>' for s, label in sorted(named, key=lambda x: x[1].lower()))
    page = head("Compare software · AirStack.bot", lead, url, ({"@context": "https://schema.org", "@type": "WebPage", "name": "Compare software", "url": url, "description": lead}, crumb))
    page = page.replace("</head>", '<meta http-equiv="refresh" content="0; url=/#/compare"></head>', 1)
    out.mkdir(parents=True, exist_ok=True)
    out.joinpath("index.html").write_text(page + f'<body><main>{nav}<h1>Compare software</h1><p class="lead">{e(lead)}</p><a class="cta" href="/#/compare">Open the comparison</a>'
                                          + (f"<h2>Ready-made comparisons</h2><ul>{pairs}</ul>" if pairs else "") + f"{foot()}</main></body></html>\n")
    return url
