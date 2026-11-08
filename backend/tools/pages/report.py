"""The static insights, calendar and method pages."""
import shutil
from airstack import paths
from .layout import BASE, breadcrumbs, e, foot, head
from airstack.files import read_json


def write(name, title, lead, body, ld):
    url = f"{BASE}/{name}/"; out = paths.PAGE_DIRS[name]
    shutil.rmtree(out, ignore_errors=True); out.mkdir()
    nav, crumb = breadcrumbs((("AirStack", "/"), (title, None)))
    out.joinpath("index.html").write_text(head(f"{title} · AirStack", lead, url, (ld | {"url": url}, crumb)) + f"<body><main>{nav}<h1>{e(title)}</h1><p class=\"lead\">{e(lead)}</p>{body}{foot()}</main></body></html>\n")
    return url


def report_pages():
    insights = read_json(paths.INSIGHTS); categories = sorted(insights["categories"].items(), key=lambda x: (-x[1]["researched"], x[1]["name"]))
    rows = "".join(f'<tr><td><a href="/c/{e(cid)}/">{e(c["name"])}</a></td><td>{c["researched"]:,} / {c["listed"]:,}</td><td>{c["free_plan"]:,}</td><td>{c["security_claim"]:,}</td><td>{c["open_source"]:,}</td></tr>' for cid, c in categories)
    lead = f"Evidence coverage across {len(categories):,} software categories, from product pages, published prices and Wikidata records."
    body = f'<h2>Category coverage</h2><table><tr><th>Category</th><th>Read / listed</th><th>Free plan stated</th><th>SOC 2 or ISO 27001 stated</th><th>Open source stated</th></tr>{rows}</table><p><small>{e(insights["source"]["note"])}</small></p>'
    urls = [write("insights", "Software market insights", lead, body, {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Software market insights", "description": lead})]

    events = read_json(paths.EVENTS); start = events["source"]["built_for"]
    upcoming = [x for x in events["events"] if x["at"] >= start and x["status"] == "scheduled"][:250]
    rows = "".join(f'<tr><td><time datetime="{e(x["at"])}">{e(x["at"])}</time></td><td>{e(x["name"])}</td><td><a href="{e(x["url"])}" rel="nofollow noopener">{e(x["title"])}</a></td><td>{e(x["status"])}</td></tr>' for x in upcoming)
    lead = f"{len(upcoming):,} externally published software dates from {start}, kept separate from observed changes."
    body = f'<h2>Upcoming dates</h2><table><tr><th>Date</th><th>Product</th><th>Event</th><th>Status</th></tr>{rows}</table><p><small>{e(events["source"]["statuses"]["scheduled"])} Every row links to its publisher.</small></p>'
    urls.append(write("calendar", "Software change calendar", lead, body, {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Software change calendar", "description": lead}))

    lead = "How AirStack turns public pages into facts: a short quote, checked against the page it came from."
    body = ('<h2>The quote check</h2><p>Every fact starts as a quote of at most 25 words from a public page. Code keeps it only if the quote '
            'appears on that page and every name and number in the value appears in the quote. A certification counts only when the quote says '
            'the product holds it; an integration only when the page or the quote presents it as one. Anything else reads “Not observed”.</p>'
            '<h2>What each fact carries</h2><p>The quote, the page it is on, the day AirStack read that page, and whether the page is the '
            'vendor’s own site, a store listing or a public registry. A fact whose quote is no longer on its page is withdrawn.</p>'
            '<h2>Check the record</h2><p><a href="/open-data/">Download the published fact records</a> or follow <a href="/changes.atom">the changes feed</a>.</p>')
    urls.append(write("method", "How AirStack builds its evidence", lead, body, {"@context": "https://schema.org", "@type": "WebPage", "name": "How AirStack builds its evidence", "description": lead}))
    return urls
