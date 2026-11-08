"""The static insights, calendar and method pages."""
import shutil
from airstack import paths
from .layout import BASE, breadcrumbs, e, foot, head
from .data import found
from airstack.files import read_json


def write(name, title, lead, body, ld):
    url = f"{BASE}/{name}/"; out = paths.PAGE_DIRS[name]
    shutil.rmtree(out, ignore_errors=True); out.mkdir()
    nav, crumb = breadcrumbs((("AirStack", "/"), (title, None)))
    out.joinpath("index.html").write_text(head(f"{title} · AirStack", lead, url, (ld | {"url": url}, crumb)) + f"<body><main>{nav}<h1>{e(title)}</h1><p class=\"lead\">{e(lead)}</p>{body}{foot()}</main></body></html>\n")
    return url


def report_pages():
    insights = read_json(paths.INSIGHTS); categories = sorted(insights["categories"].items(), key=lambda x: (-x[1]["researched"], x[1]["name"]))
    rows = "".join(f'<tr><td><a href="/c/{e(cid)}/">{e(c["name"])}</a></td><td>{c["researched"]:,} / {c["listed"]:,}</td><td>{found(c["free_plan"], c["researched"])}</td><td>{found(c["open_source"], c["researched"])}</td></tr>' for cid, c in categories)
    lead = f"Evidence coverage across {len(categories):,} software categories, from product pages, published prices and Wikidata records."
    F = insights.get("findings", {})
    pc = lambda x: f"{x * 100:.0f}%"
    items = [("Rising attention", i["name"], i["node"], f'{pc(i["value"])} of views, was {pc(i["baseline"])}; driven by {i["driver"]["name"]}; {i["base"]:,} products measured') for i in F.get("rising", {}).get("items", [])[:5]]
    items += [("Where AI is moving in", i["name"], i["node"], f'{pc(i["value"])} state AI in their one-liner vs {pc(i["baseline"])} average; {i["found"]:,} of {i["base"]:,} read') for i in F.get("ai", {}).get("items", [])[:5]]
    items += [("New entrants", i["name"], i["node"], f'{pc(i["value"])} started recently vs {pc(i["baseline"])} average; {i["found"]:,} of {i["base"]:,}') for i in F.get("entrants", {}).get("items", [])[:5]]
    items += [("Standout trait", i["name"], i["node"], f'{pc(i["value"])} {i["label"]} vs {pc(i["baseline"])} average; {i["found"]:,} of {i["base"]:,} read') for i in F.get("standout", {}).get("items", [])[:5]]
    shown = "".join(f'<tr><td>{e(k)}</td><td><a href="/t/{e(node)}/">{e(name)}</a></td><td>{e(text)}</td></tr>' for k, name, node, text in items)
    body = (f'<h2>What stands out</h2><table><tr><th>Comparison</th><th>Category</th><th>Against its baseline, with its base</th></tr>{shown}</table>' if shown else '') + f'<h2>Category coverage</h2><table><tr><th>Category</th><th>Read / listed</th><th>Free plan stated</th><th>Open source stated</th></tr>{rows}</table><p><small>{e(insights["source"]["note"])}</small></p>'
    urls = [write("insights", "Software market insights", lead, body, {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Software market insights", "description": lead})]

    events = read_json(paths.EVENTS); start = events["source"]["built_for"]
    upcoming = [x for x in events["events"] if x["at"] >= start and x["status"] == "scheduled" and not x["kind"].startswith("end of")][:250]
    rows = "".join(f'<tr><td><time datetime="{e(x["at"])}">{e(x["at"])}</time></td><td>{e(x["name"])}</td><td><a href="{e(x["url"])}" rel="nofollow noopener">{e(x["title"])}</a></td><td>{e(x["status"])}</td></tr>' for x in upcoming)
    lead = f"{len(upcoming):,} software launches and releases dated by their sources from {start}, kept separate from observed changes."
    body = f'<h2>Upcoming dates</h2><table><tr><th>Date</th><th>Product</th><th>Event</th><th>Status</th></tr>{rows}</table><p><small>{e(events["source"]["statuses"]["scheduled"])} Every row links to its publisher.</small></p>'
    urls.append(write("calendar", "Software change calendar", lead, body, {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Software change calendar", "description": lead}))

    lead = "Every fact on AirStack is a short quote from the product's own page, with the page and the day it was read."
    body = ('<h2>Quoted, dated, linked</h2><p>Each fact is the vendor’s own words, linked to where they appear on its page, '
            'with the days AirStack read and re-checked it. When a page no longer says it, the fact is withdrawn.</p>'
            '<h2>What we leave out</h2><p>AirStack does not republish security, compliance or customer claims, which only the vendor can stand behind, '
            'and shows a list price only with the date it was listed.</p>'
            '<h2>Unknown stays unknown</h2><p>Where a page does not say, AirStack shows “Not observed”, never a guess or a zero.</p>'
            '<h2>Signals compare a product with its own past</h2><p>Movement is a product against its own earlier weeks, never a score against others. '
            'A missing week stays missing.</p>'
            '<h2>Check the record</h2><p><a href="/open-data/">Download the published fact records</a> or follow <a href="/changes.atom">the changes feed</a>.</p>')
    urls.append(write("method", "How AirStack checks its facts", lead, body, {"@context": "https://schema.org", "@type": "WebPage", "name": "How AirStack checks its facts", "description": lead}))
    return urls
