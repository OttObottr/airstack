# spec: AS-251 AS-252 AS-257 AS-285 AS-295 AS-316 AS-317 AS-318 AS-319
"""/c/<category>/: the guide, the numbers and every product with a page in one category."""
import json, shutil
from airstack import paths
from .layout import BASE, e, foot, head, trim
from .data import CATS, PAGES, starting

def cat_page(cid, name, items, prices, oss, hf, guide, ins, kpis):
    url = f"{BASE}/c/{cid}/"; G = guide or {}; I = ins or {}
    rows = []
    for x in items:
        q = prices.get(x["id"]); paid, free = starting(q)
        what = (x["profile"] or {}).get("what_it_does", {}).get("value") if x["profile"] and x["profile"].get("what_it_does") else x.get("description")
        price = (f'<a href="{e(q["url"])}" rel="nofollow noopener" title="{e(paid["quote"])}">{e(paid["price"])}</a> <small>{e(paid["plan"])}{" · per user" if paid["unit"] == "user" else ""}{" / month" if paid["period"] == "month" else " / year" if paid["period"] == "year" else ""}</small>'
                 if paid else "") + (" <small>free plan</small>" if free else "")
        rows.append(f'<tr><td><a href="/p/{e(x["slug"])}/">{e(x["name"])}</a></td><td>{e(trim(what)) if what else "<small>Not observed</small>"}</td><td>{price or "<small>Not observed</small>"}</td></tr>')
    kp = "".join(f'<tr><th>{e(k["label"])}</th><td>{I.get(k["key"], 0)} of {I.get("researched", 0)} researched</td></tr>' for k in kpis) if I.get("researched") else ""
    med = I.get("median_seat")
    vetted = [r for r in (oss.get("categories", {}).get(cid) or []) if r.get("vetted")][:6]
    TASKS = PAGES["category_models"]
    models = [m for t in TASKS.get(cid, []) for m in (hf.get("tasks", {}).get(t, {}).get("models") or [])[:3]]
    desc = (f"{G.get('what', '')} " + f"{len(items)} products compared on AirStack" + (f"; {I['free_plan']} of {I['researched']} researched state a free plan" if I.get("researched") else "")
            + (f"; the median list price is {med['price']} per user a month ({med['name']})" if med else "") + ".").strip()
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": name, "url": url, "description": desc[:300],
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{BASE}/p/{x['slug']}/", "name": x["name"]} for i, x in enumerate(items)]}}
    title = f"{name}: products, prices and open-source alternatives · AirStack"
    li = lambda xs: "".join(f"<li>{e(v)}</li>" for v in xs)
    def candidate(r):
        hn = (r.get("community") or {}).get("hacker_news") or {}
        discussed = "" if hn.get("status") != "observed" else "<br><small>Discussed on Hacker News: " + " · ".join(
            f'<a href="{e(i["discussion"])}" rel="nofollow noopener">{e(i["title"])}</a> ({i["points"]} points, {i["comments"]} comments, {e(i["date"])})'
            for i in hn["items"]) + "</small>"
        return (f'<li><a href="{e(r["url"])}" rel="nofollow noopener">{e(r["repo"])}</a> '
                f'<small>OpenSSF Scorecard {r["scorecard"]["score"]:.1f}/10 · {e(r["license"] or "licence not stated")} · '
                f'{r["forks"]:,} forks · {r["open_issues_and_pull_requests"]:,} open issues and pull requests</small>{discussed}</li>')
    return head(title, desc, url, (ld,)) + f"""<body><main><nav><a href="/">AirStack</a> › {e(I.get("department") or "Categories")}</nav>
<h1>{e(name)}</h1>{f'<p class="lead">{e(G["what"])}</p>' if G.get("what") else ''}
<a class="cta" href="/">Search AirStack</a>
{f'<h2>Why teams use it</h2><ul>{li(G.get("why", []))}</ul><p><small>Who uses it: {e(", ".join(G.get("who", [])))}. Watch for: {e(G.get("watch_for", ""))} AirStack’s guide to the category.</small></p>' if G else ''}
{f'<h2>{e(name)} in numbers</h2><table>{kp}</table>' + (f'<p><small>Median list price per user a month: <a href="{e(med["url"])}" rel="nofollow noopener">{e(med["price"])}</a> ({e(med["name"])} {e(med["plan"])}), across {med["of"]} products with a published per-user price. Shares count what each product’s own pages state.</small></p>' if med else '') if kp else ''}
<h2>{len(items)} products</h2><table><tr><th>Product</th><th>What it says it does</th><th>Starting at</th></tr>{"".join(rows)}</table>
<p><small>Prices are list prices as written on each pricing page; hover one for its quote. “Not observed” means AirStack has not found it on that product’s pages.</small></p>
{'<h2>Open-source candidates</h2><ul>' + "".join(candidate(r) for r in vetted) + '</ul><p><small>Repository activity is not use or trust. Projects shown pass OpenSSF Scorecard’s automated checks. Automated checks, not an audit.</small></p>' if vetted else ''}
{'<h2>Open models for the job</h2><ul>' + "".join(f'<li><a href="{e(m["url"])}" rel="nofollow noopener">{e(m["id"])}</a> <small>{m["downloads"]:,} downloads in 30 days · {e(m["license"] or "licence not stated")}</small></li>' for m in models) + '</ul>' if models else ''}
{foot()}
</main></body></html>
"""

def cat_pages(all_, prices, oss):
    """A page per category: the guide, the numbers, every product with a page, its sourced starting price, open-source candidates and open models."""
    site = paths.read_js(paths.SITE_DATA); names = {c["id"]: c["name"] for c in site.get("cats", [])} | {l["id"]: l["name"] for l in site["lanes"]}
    guides = json.loads(paths.CATEGORY_GUIDES.read_text())["categories"] if paths.CATEGORY_GUIDES.exists() else {}
    ins = json.loads(paths.INSIGHTS.read_text()) if paths.INSIGHTS.exists() else {"categories": {}, "kpis": []}
    hf = json.loads(paths.HF.read_text()) if paths.HF.exists() else {}
    out = paths.PAGE_DIRS["c"]; shutil.rmtree(out, ignore_errors=True); urls = []
    for cid, name in names.items():
        items = sorted((x for x in all_.values() if x["lane"] == cid and x.get("page")), key=lambda x: (-((x["profile"] or {}).get("facts") or 0), x["name"].lower()))
        if not items:
            continue
        CATS.add(cid)
        d = out / cid; d.mkdir(parents=True, exist_ok=True)
        d.joinpath("index.html").write_text(cat_page(cid, name, items, prices, oss, hf, guides.get(cid), ins["categories"].get(cid), ins.get("kpis", [])))
        urls.append((f"{BASE}/c/{cid}/", "2026-11-05"))
    return urls
