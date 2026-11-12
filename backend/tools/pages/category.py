"""/c/<category>/: the guide, the numbers and every product with a page in one category."""
import shutil
from airstack import paths
from .layout import BASE, breadcrumbs, e, foot, head, trim
from .data import CATS, found, listed
from airstack.files import read_json

def cat_page(cid, name, items, prices, oss, guide, guide_source, ins, kpis):
    url = f"{BASE}/c/{cid}/"; G = guide or {}; idx = ins or {}
    rows = []
    for x in items:
        q = prices.get(x["id"])
        what = (x["profile"] or {}).get("what_it_does", {}).get("value") if x["profile"] and x["profile"].get("what_it_does") else x.get("description")
        price = f"<small>{listed(q)}</small>" if q else ""
        rows.append(f'<tr><td><a href="/p/{e(x["slug"])}/">{e(x["name"])}</a></td><td>{e(trim(what)) if what else "<small>Not observed</small>"}</td><td>{price or "<small>Not observed</small>"}</td></tr>')
    kp = "".join(f'<tr><th>{e(k["label"])}</th><td>{found(idx.get(k["key"], 0), idx["researched"])} researched</td></tr>' for k in kpis) if idx.get("researched") else ""
    vetted = [r for r in (oss.get("categories", {}).get(cid) or []) if r.get("vetted")][:6]
    desc = (f"{G.get('what', '')} " + f"{len(items)} products compared on AirStack" + (f"; {found(idx['free_plan'], idx['researched'])} researched state a free plan" if idx.get("researched") else "")
            + ".").strip()
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": name, "url": url, "description": desc[:300],
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{BASE}/p/{x['slug']}/", "name": x["name"]} for i, x in enumerate(items)]}}
    title = f"{name}: products and prices{' with open-source alternatives' if vetted else ''} · AirStack.bot"
    nav, crumb = breadcrumbs((("AirStack", "/"), ("Categories", "/c/"), (name, None)))
    li = lambda xs: "".join(f"<li>{e(v)}</li>" for v in xs)
    def candidate(r):
        return (f'<li><a href="{e(r["url"])}" rel="nofollow noopener">{e(r["repo"].split("/")[-1])}</a> '
                f'<small>OpenSSF Scorecard {r["scorecard"]["score"]:.1f}/10 · {e(r["license"] or "licence not stated")} · '
                f'{r["forks"]:,} forks · {r["open_issues_and_pull_requests"]:,} open issues and pull requests</small></li>')
    return head(title, desc, url, (ld, crumb)) + f"""<body><main>{nav}
<h1>{e(name)}</h1>{f'<p class="lead">{e(G["what"])}</p>' if G.get("what") else ''}
<a class="cta" href="/">Search AirStack</a>
{f'<h2>Why teams use it</h2><ul>{li(G.get("why", []))}</ul><p><small>Who uses it: {e(", ".join(G.get("who", [])))}. Watch for: {e(G.get("watch_for", ""))} {e(guide_source.get("note", "AirStack’s guide to the category."))} Written <time datetime="{e(guide_source.get("written", ""))}">{e(guide_source.get("written", ""))}</time>.</small></p>' if G else ''}
{f'<h2>{e(name)} in numbers</h2><table>{kp}</table><p><small>Shares count what each product’s own pages state.</small></p>' if kp else ''}
<h2>{len(items)} products</h2><table><tr><th>Product</th><th>What it says it does</th><th>List prices</th></tr>{"".join(rows)}</table>
<p><small>Vendor statements, quoted and dated; not verified by AirStack. “Not observed” means AirStack has not found it on that product’s pages.</small></p>
{'<h2>Open-source candidates</h2><ul>' + "".join(candidate(r) for r in vetted) + '</ul><p><small>Repository activity is not use or trust. Projects shown pass OpenSSF Scorecard’s automated checks. Automated checks, not an audit.</small></p>' if vetted else ''}
{foot()}
</main></body></html>
"""

def cat_pages(all_, prices, oss):
    site = paths.read_js(paths.SITE_DATA); names = {c["id"]: c["name"] for c in site.get("cats", [])} | {ln["id"]: ln["name"] for ln in site["lanes"]}
    guide_data = read_json(paths.CATEGORY_GUIDES) if paths.CATEGORY_GUIDES.exists() else {"source": {}, "categories": {}}
    guides, guide_source = guide_data["categories"], guide_data["source"]
    ins = read_json(paths.INSIGHTS) if paths.INSIGHTS.exists() else {"categories": {}, "kpis": []}
    out = paths.PAGE_DIRS["c"]; shutil.rmtree(out, ignore_errors=True); urls, made = [], []
    for cid, name in names.items():
        items = sorted((x for x in all_.values() if x["lane"] == cid and x.get("page")), key=lambda x: (-((x["profile"] or {}).get("facts") or 0), x["name"].lower()))
        if not items:
            continue
        CATS.add(cid)
        d = out / cid; d.mkdir(parents=True, exist_ok=True)
        d.joinpath("index.html").write_text(cat_page(cid, name, items, prices, oss, guides.get(cid), guide_source, ins["categories"].get(cid), ins.get("kpis", [])))
        urls.append(f"{BASE}/c/{cid}/")
        made.append((cid, name, len(items)))
    url = f"{BASE}/c/"; lead = f"Browse {len(made):,} software categories and the {sum(n for _, _, n in made):,} researched products in them."
    nav, crumb = breadcrumbs((("AirStack", "/"), ("Categories", None)))
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Software categories", "url": url, "description": lead,
          "mainEntity": {"@type": "ItemList", "numberOfItems": len(made), "itemListElement": [{"@type": "ListItem", "position": i, "name": name, "url": f"{BASE}/c/{cid}/"} for i, (cid, name, _) in enumerate(made, 1)]}}
    links = "".join(f'<li><a href="/c/{e(cid)}/">{e(name)}</a> <small>{n:,} researched products</small></li>' for cid, name, n in made)
    out.mkdir(exist_ok=True); out.joinpath("index.html").write_text(head("Software categories · AirStack.bot", lead, url, (ld, crumb)) + f"<body><main>{nav}<h1>Software categories</h1><p class=\"lead\">{e(lead)}</p><ul>{links}</ul>{foot()}</main></body></html>\n")
    return [url] + urls
