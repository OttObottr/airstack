# spec: AS-252 AS-257 AS-285 AS-316 AS-317 AS-318 AS-319
"""/compare/<a>-vs-<b>/: two products side by side from what their own pages state."""
import json, shutil
from airstack import paths
from .layout import BASE, e, foot, head
from .data import LABELS, PAGES, PAIRS, starting, value

SHARED = PAGES["shared_facts"]                                                          # a pair earns a page only when both products' own pages state at least this many of the same facts

def pair_slug(a, b):
    x, y = sorted([a, b], key=lambda z: z["slug"]); return f"{x['slug']}-vs-{y['slug']}", x, y

def cell(P, k):
    c = P.get(k) if P else None
    if not c:
        return "<small>Not observed</small>"
    src = " ".join(f'<a href="{e(s_["url"])}" rel="nofollow noopener">{e(s_["host"])}</a>' for s_ in c.get("sources", [])[:1])
    return f"{e(value(c))} <small>{src}</small>"

def price_cell(q):
    paid, free = starting(q)
    out = (f'<a href="{e(q["url"])}" rel="nofollow noopener" title="{e(paid["quote"])}">{e(paid["price"])}</a> <small>{e(paid["plan"])}{" · per user" if paid["unit"] == "user" else ""}{" / month" if paid["period"] == "month" else " / year" if paid["period"] == "year" else ""}</small>' if paid else "")
    return (out + (" <small>free plan listed</small>" if free else "")) or "<small>Not observed</small>"

def differences(a, b, qa, qb):
    """Plain statements of what one product's own pages state and the other's don't. Nothing is scored or ranked."""
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
    rows = [("What it says it does", cell(a["profile"], "what_it_does"), cell(b["profile"], "what_it_does")), ("Starting at", price_cell(qa), price_cell(qb))]
    rows += [(lab, cell(a["profile"], k), cell(b["profile"], k)) for k, lab in LABELS[1:] if (a["profile"] or {}).get(k) or (b["profile"] or {}).get(k)]
    table = "".join(f"<tr><th>{e(l)}</th><td>{x}</td><td>{y}</td></tr>" for l, x, y in rows)
    diff = differences(a, b, qa, qb)
    pa, pb = starting(qa)[0], starting(qb)[0]
    desc = (f"{a['name']} vs {b['name']}, from each product’s own pages: " + "; ".join(x for x in [f"{a['name']} from {pa['price']}" if pa else "", f"{b['name']} from {pb['price']}" if pb else ""] if x)
            + (". " if pa or pb else "") + (diff[0] if diff else "Plans, platforms, integrations and security claims, side by side.")).strip()
    title = f"{a['name']} vs {b['name']}: plans, prices and features compared · AirStack"
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": f"{a['name']} vs {b['name']}", "url": url, "description": desc[:300],
          "about": [{"@type": "SoftwareApplication", "name": x["name"], "url": f"{BASE}/p/{x['slug']}/", "applicationCategory": x["category"]} for x in (a, b)]}
    return slugv, head(title, desc, url, (ld,)) + f"""<body><main><nav><a href="/">AirStack</a> › <a href="/c/{e(a["lane"])}/">{e(cat)}</a></nav>
<h1>{e(a['name'])} vs {e(b['name'])}</h1>
<p class="lead">What each one’s own pages state, side by side. Every value is a quote AirStack found on that product’s pages; “Not observed” means AirStack has not found it on that product’s pages.</p>
<table><tr><th></th><th><a href="/p/{e(a['slug'])}/">{e(a['name'])}</a></th><th><a href="/p/{e(b['slug'])}/">{e(b['name'])}</a></th></tr>{table}</table>
{'<h2>Where they differ</h2><ul>' + "".join(f"<li>{e(d)}</li>" for d in diff) + '</ul>' if diff else ''}
<p><small>Prices are list prices as written on each pricing page; check them before you buy. Nothing here is a ranking or a recommendation.</small></p>
{foot()}
</main></body></html>
"""

def compare_pages(all_, prices):
    """Every pair of researched products in the same category whose own pages state at least SHARED of the same facts: a side-by-side
    worth reading. Pairs with less in common would be two thin columns, so they get no page; more research makes more pairs, by itself."""
    ins = json.loads(paths.INSIGHTS.read_text()) if paths.INSIGHTS.exists() else {"map": {"points": []}}
    docs = {pt[0]: pt[3] for pt in ins["map"]["points"]}
    out = paths.PAGE_DIRS["compare"]; shutil.rmtree(out, ignore_errors=True); urls = []
    site = paths.read_js(paths.SITE_DATA); cats = {c["id"]: c["name"] for c in site.get("cats", [])}
    for cid, cname in cats.items():
        top = sorted((x for x in all_.values() if x["lane"] == cid and x.get("page") and x["profile"] and (x["profile"].get("facts") or 0) >= 5),
                     key=lambda x: (-docs.get(x["id"], 0), -(x["profile"].get("facts") or 0), x["name"].lower()))
        for i, a in enumerate(top):
            for b in top[i + 1:]:
                if sum(1 for k, _ in LABELS if a["profile"].get(k) and b["profile"].get(k)) < SHARED:
                    continue
                slugv, h = compare_page(a, b, prices, cname)
                d = out / slugv; d.mkdir(parents=True, exist_ok=True); d.joinpath("index.html").write_text(h)
                for x, y in ((a, b), (b, a)): PAIRS.setdefault(x["id"], []).append((y, slugv))
                urls.append((f"{BASE}/compare/{slugv}/", "2026-11-05"))
    return urls
