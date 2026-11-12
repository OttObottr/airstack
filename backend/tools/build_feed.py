"""changes.atom (observed changes over news.json's window_days) and the monthly open-data release, from the published files.
Usage: python backend/tools/build_feed.py"""
import gzip
import json
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from airstack import paths
from airstack.evidence import shown
from airstack.files import read_json

from pages.layout import WIKIMEDIA, breadcrumbs, e, foot, head, slug as page_slug

BASE, ATOM, TAG = "https://airstack.bot", "http://www.w3.org/2005/Atom", "tag:airstack.bot,2026:"
SCHEDULE = "From {}’s support schedule on endoflife.date."
SAYS = {"changelog": "From {}’s own changelog.", "blog": "From {}’s own blog or news feed.", "release": "A GitHub release of {}.", "end of life": SCHEDULE, "end of active support": SCHEDULE, "end of extended support": SCHEDULE}
NOT_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")
slug = lambda s: page_slug(s, 80)
tag = lambda url: TAG + urllib.parse.quote(url, safe="/:?@!$&'()*+,;=%-._~")  # RFC 4151 tag URI

def rfc3339(d):
    t = datetime.fromisoformat(d.replace("Z", "+00:00"))
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def changes(news, events, pages):
    """The feed's entries, newest first. `pages` maps a product id to its page slug (only products that have a page)."""
    end = date.fromisoformat(news["source"].get("read") or events["source"]["built_for"])
    start = (end - timedelta(days=news["source"]["window_days"])).isoformat()
    in_news = {i["url"] for i in news["items"]}
    rows = [(tag(i["url"]), i) for i in news["items"]]
    rows += [(tag(e["url"]) + "#" + slug(e["title"] or ""), {**e, "date": e["at"]}) for e in events["events"]  # one support page lists many cycles
             if e["status"] == "observed" and e.get("url") and e["url"] not in in_news]
    out = {}
    for id_, i in rows:
        if id_ in out or not start < i["date"][:10] <= end.isoformat():
            continue
        title = i["title"] or f"{i['name']} {i.get('version') or ''}"
        out[id_] = {"id": id_, "title": NOT_XML.sub("", title).strip(), "link": i["url"], "updated": rfc3339(i["date"]), "name": i["name"],
                    "kind": i["kind"], "page": pages.get(i["id"])}
    return sorted(sorted(out.values(), key=lambda x: x["id"]), key=lambda x: x["updated"], reverse=True)[:paths.config("pages")["limits"]["feed_entries"]]

def atom(entries, end, days):
    q = lambda t: f"{{{ATOM}}}{t}"
    def sub(parent, name, text=None, **attrs):
        el = ET.SubElement(parent, q(name), attrs)
        if text is not None: el.text = NOT_XML.sub("", text)
        return el
    ET.register_namespace("", ATOM)
    feed = ET.Element(q("feed"))
    sub(feed, "id", TAG + "changes"); sub(feed, "title", "AirStack: what changed")
    sub(feed, "subtitle", f"Changelogs, releases and announcements from the products AirStack tracks, in the last {days} days, each linked to its source.")
    sub(feed, "link", rel="self", type="application/atom+xml", href=f"{BASE}/changes.atom"); sub(feed, "link", rel="alternate", type="text/html", href=f"{BASE}/")
    sub(feed, "updated", entries[0]["updated"] if entries else f"{end}T00:00:00Z")
    a = sub(feed, "author"); sub(a, "name", "AirStack"); sub(a, "uri", f"{BASE}/")
    sub(feed, "rights", "Titles remain their publishers' property. Original compilation metadata is CC BY 4.0 where applicable.")
    for x in entries:
        e = sub(feed, "entry")
        sub(e, "id", x["id"]); sub(e, "title", x["title"], type="text"); sub(e, "updated", x["updated"])
        sub(e, "link", rel="alternate", type="text/html", href=x["link"])
        if x["page"]: sub(e, "link", rel="related", type="text/html", href=f"{BASE}/p/{x['page']}/", title=f"{x['name']} on AirStack")
        sub(e, "category", term=x["kind"]); sub(e, "summary", SAYS[x["kind"]].format(x["name"]) if x["kind"] in SAYS else f"{x['name']}: {x['kind']}.", type="text")
    ET.indent(feed)
    return ('<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(feed, encoding="unicode") + "\n").encode()

OPEN_FIELDS = ("id", "name", "metric", "value", "quote", "url", "read", "licence")
LICENCE = "Original record metadata: CC BY 4.0 where applicable. Quote: publisher's words, linked to source."
LICENCE_WIKIMEDIA = "Original record metadata: CC BY 4.0 where applicable. Quote: CC BY-SA 4.0, linked to Wikimedia source."

def open_lines(chain):
    """One JSON line per published fact: the quote, never the page."""
    rows = {json.dumps({"id": pid, "name": e["name"], "metric": f["metric"], "value": f["value"], "quote": f["quote"], "url": f["url"], "read": f["retrieved"],
                        "licence": LICENCE_WIKIMEDIA if WIKIMEDIA.search(f["host"]) else LICENCE}, ensure_ascii=False, sort_keys=True)
            for pid, e in chain["entities"].items() for f in e["facts"] if shown(chain["policy"], f["metric"])}
    return sorted(rows)

def pack(lines):
    return gzip.compress("".join(ln + "\n" for ln in lines).encode(), mtime=0)

def unpack(blob):
    return gzip.decompress(blob).decode().splitlines()

def same(name, blob, old):
    """A release compares by its lines: another zlib may compress the same lines to other bytes."""
    return old == blob or (name.endswith(".gz") and unpack(old) == unpack(blob))

def readme(releases):
    rows, prev = [], set()
    for name, lines in sorted(releases.items()):
        now = set(lines)
        rows.append(f"| `{name}` | {len(now):,} | {len({json.loads(ln)['id'] for ln in now}):,} | {len(now - prev):,} | {len(prev - now):,} |")
        prev = now
    return """# AirStack open data

Facts from products' own pages and public registries, one JSON line per fact, released each month as `airstack-<YYYY-MM>.jsonl.gz`.
Each fact is a short quote with its source link and the day the page was read, so anyone can check it.

## Licence

- AirStack's compilation (the records, their selection and arrangement) is under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
  Credit "AirStack (https://airstack.bot)" and keep each fact's source link.
- Quotes belong to their publishers. Each is at most 25 words and is included only to show where a fact comes from. Text quoted from
  Wikipedia or another Wikimedia project is under CC BY-SA 4.0; each line's `licence` says which applies.
- Product ids that start with `Q` are Wikidata items. Those ids and their names come from [Wikidata](https://www.wikidata.org/), under CC0.
- Product names are trademarks of their owners. A publisher can ask for a quote to be removed by opening an issue at
  https://github.com/OttObottr/airstack/issues.

## Fields

| Field | What it holds |
|---|---|
| `id` | AirStack's product id |
| `name` | The product's name |
| `metric` | What the fact is about, such as `what_it_does`, `platforms`, `integrations` or `free_plan` |
| `value` | The value read from the quote: text, a list, true or false, or a number |
| `quote` | The page's own words, at most 25 words |
| `url` | The page the quote is on |
| `read` | The day AirStack read that page (YYYY-MM-DD) |
| `licence` | The licence note for this line |

Not included: the stored page text and prices. Facts come from pages AirStackBot read while their robots.txt allowed it, and not
from hosts whose terms AirStack has recorded as barring automated reading.

## How it is built

`backend/tools/build_feed.py` reads `chain-data.json`, the evidence file the site serves, and writes this month's release and this file.
It makes no model call and no network request, and the same input gives the same bytes. The release for a month is the last build in it.

## Releases

| Release | Facts | Products | New since the previous release | Gone since the previous release |
|---|---|---|---|---|
""" + "\n".join(rows) + "\n"


def open_page(releases):
    name, lines = sorted(releases.items())[-1]
    facts = [json.loads(line) for line in lines]; reads = sorted({f["read"] for f in facts})
    url, download = f"{BASE}/open-data/", f"{BASE}/open-data/{name}"
    lead = f"{len(facts):,} source-linked software facts across {len({f['id'] for f in facts}):,} products, released as compressed JSON Lines."
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": "AirStack software facts", "description": lead, "url": url,
          "license": "https://creativecommons.org/licenses/by/4.0/", "dateModified": reads[-1], "temporalCoverage": f"{reads[0]}/{reads[-1]}",
          "creator": {"@type": "Organization", "name": "AirStack", "url": f"{BASE}/"},
          "distribution": {"@type": "DataDownload", "contentUrl": download, "encodingFormat": "application/gzip"}}
    nav, crumb = breadcrumbs((("AirStack", "/"), ("Open data", None)))
    fields = "".join(f"<li><code>{x}</code></li>" for x in OPEN_FIELDS)
    rows = "".join(f'<tr><td><a href="{e(n)}">{e(n)}</a></td><td>{len(ls):,}</td><td>{len({json.loads(line)["id"] for line in ls}):,}</td></tr>' for n, ls in sorted(releases.items(), reverse=True))
    return (head("Open software market data · AirStack.bot", lead, url, (ld, crumb)) + f"""<body><main>{nav}<h1>AirStack open data</h1><p class="lead">{e(lead)}</p>
<p>Each line contains a short source quote, the normalized fact it supports, its source URL, and the day AirStack read it.</p>
<h2>Downloads</h2><table><tr><th>Release</th><th>Facts</th><th>Products</th></tr>{rows}</table>
<h2>Fields</h2><ul>{fields}</ul>
<h2>Licence</h2><p>AirStack’s original compilation metadata is available under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Quotes and trademarks remain their owners’ property. Keep each source link with its fact.</p>
{foot()}</main></body></html>\n""").encode()

def build():
    """Every output as {path under data/site: bytes}."""
    import build_pages
    all_ = build_pages.products()
    pages = {k: p["slug"] for k, p in build_pages.built(all_, build_pages.own_prices(all_, read_json(paths.PRICING) if paths.PRICING.exists() else {})).items()}
    news, events = read_json(paths.NEWS), read_json(paths.EVENTS)
    out = {"changes.atom": atom(changes(news, events, pages), news["source"].get("read") or events["source"]["built_for"], news["source"]["window_days"])}
    chain = read_json(paths.CHAIN_DATA)
    lines = open_lines(chain)
    releases = {f.name: [ln for ln in unpack(f.read_bytes()) if shown(chain["policy"], json.loads(ln)["metric"])] for f in sorted(paths.OPEN_DATA.glob("airstack-*.jsonl.gz"))}
    releases[f"airstack-{max(json.loads(ln)['read'] for ln in lines)[:7]}.jsonl.gz"] = lines
    out |= {f"open-data/{name}": pack(ls) for name, ls in releases.items()}
    out["open-data/README.md"] = readme(releases).encode()
    out["open-data/index.html"] = open_page(releases)
    return out

def main():
    out = build()
    for name, blob in out.items():
        p = paths.SITE / name; p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists() or not same(name, blob, p.read_bytes()):
            p.write_bytes(blob)
    n = len(ET.fromstring(out["changes.atom"]).findall(f"{{{ATOM}}}entry"))
    print(f"changes.atom: {n} entries; "
          + "; ".join(f"{k}: {len(unpack(v)):,} facts" for k, v in out.items() if k.endswith(".jsonl.gz")))

if __name__ == "__main__":
    sys.exit(main())
