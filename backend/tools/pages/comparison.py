"""/compare/<a>-vs-<b>/: two products side by side from their own pages."""
import shutil
from airstack import paths
from .layout import BASE, breadcrumbs, e, foot, head
from .data import LABELS, PAGES, PAIRS, TAXON, proof, starting, value
from airstack.files import read_json

SHARED = PAGES["shared_facts"]  # a pair gets a page only with at least this many facts stated on both sides

def pair_slug(a, b):
    x, y = sorted([a, b], key=lambda z: z["slug"]); return f"{x['slug']}-vs-{y['slug']}", x, y

def cell(p, k):
    P = p["profile"]
    c = P.get(k) if P else None
    if not c:
        return "<small>Not observed</small>"
    return f"{e(value(c))}{proof(p['id'], k, c)}"

def price_cell(q):
    paid, free = starting(q)
    out = (f'<a href="{e(q["url"])}" rel="nofollow noopener" title="{e(paid["quote"])}">{e(paid["price"])}</a> <small>{e(paid["plan"])}{" · per user" if paid["unit"] == "user" else ""}{" / month" if paid["period"] == "month" else " / year" if paid["period"] == "year" else ""}<br><q>{e(paid["quote"])}</q> · read <time datetime="{e(q["checked"])}">{e(q["checked"])}</time></small>' if paid else "")
    return (out + (" <small>free plan listed</small>" if free else "")) or "<small>Not observed</small>"

def differences(a, b):
    """What one product's own pages state and the other's don't. Nothing is ranked."""
    A, B, out = a["profile"] or {}, b["profile"] or {}, []
    for k, label in (("free_plan", "a free plan"), ("open_source", "that it is open source")):
        va, vb = (A.get(k) or {}).get("value") is True, (B.get(k) or {}).get("value") is True
        if va != vb: out.append(f"{(a if va else b)['name']}’s pages state {label}; AirStack has not found that on {(b if va else a)['name']}’s pages.")
    sec = lambda P: {x for x in ("SOC 2", "ISO 27001", "HIPAA", "GDPR") if any(x.replace(" ", "").lower() in str(v).replace(" ", "").lower() for v in ((P.get("compliance") or {}).get("value") or []))}
    for x in sorted(sec(A) ^ sec(B)):
        has, lacks = (a, b) if x in sec(A) else (b, a)
        out.append(f"{has['name']} claims {x} on its own pages; {lacks['name']}’s pages read by AirStack do not mention it.")
    return out[:8]

def compare_page(a, b, prices, cat):
    slugv, a, b = pair_slug(a, b); url = f"{BASE}/compare/{slugv}/"; qa, qb = prices.get(a["id"]), prices.get(b["id"])
    rows = [("What it says it does", cell(a, "what_it_does"), cell(b, "what_it_does")), ("Starting at", price_cell(qa), price_cell(qb))]
    rows += [(lab, cell(a, k), cell(b, k)) for k, lab in LABELS[1:] if (a["profile"] or {}).get(k) or (b["profile"] or {}).get(k)]
    table = "".join(f"<tr><th>{e(ln)}</th><td>{x}</td><td>{y}</td></tr>" for ln, x, y in rows)
    diff = differences(a, b)
    pa, pb = starting(qa)[0], starting(qb)[0]
    desc = (f"{a['name']} vs {b['name']}, from each product’s own pages: " + "; ".join(x for x in [f"{a['name']} from {pa['price']}" if pa else "", f"{b['name']} from {pb['price']}" if pb else ""] if x)
            + (". " if pa or pb else "") + (diff[0] if diff else "Plans, platforms, integrations and security claims, side by side.")).strip()
    title = f"{a['name']} vs {b['name']}: plans, prices and features compared · AirStack"
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": f"{a['name']} vs {b['name']}", "url": url, "description": desc[:300],
          "about": [{"@type": "SoftwareApplication", "name": x["name"], "url": f"{BASE}/p/{x['slug']}/", "applicationCategory": x["category"]} for x in (a, b)]}
    nav, crumb = breadcrumbs((("AirStack", "/"), ("Categories", "/c/"), (cat, f'/c/{a["lane"]}/'), (f"{a['name']} vs {b['name']}", None)))
    return slugv, head(title, desc, url, (ld, crumb)) + f"""<body><main>{nav}
<h1>{e(a['name'])} vs {e(b['name'])}</h1>
<p class="lead">What each one’s own pages state, side by side. Every value is derived from its cited quote; “Not observed” means AirStack has not found it on that product’s pages.</p>
<table><tr><th></th><th><a href="/p/{e(a['slug'])}/">{e(a['name'])}</a></th><th><a href="/p/{e(b['slug'])}/">{e(b['name'])}</a></th></tr>{table}</table>
{'<h2>How do ' + e(a['name']) + ' and ' + e(b['name']) + ' differ?</h2><ul>' + "".join(f"<li>{e(d)}</li>" for d in diff) + '</ul>' if diff else ''}
<p><small>Prices are list prices as written on each pricing page; check them before you buy. Nothing here is a ranking or a recommendation.</small></p>
{foot()}
</main></body></html>
"""

def compare_pages(all_, prices):
    """Pairs in one category and one software type whose own pages state at least SHARED of the same facts."""
    ins = read_json(paths.INSIGHTS) if paths.INSIGHTS.exists() else {"map": {"points": []}}
    docs = {pt[0]: pt[3] for pt in ins["map"]["points"]}
    out = paths.PAGE_DIRS["compare"]; shutil.rmtree(out, ignore_errors=True); urls = []
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
                urls.append(f"{BASE}/compare/{slugv}/")
    return urls
