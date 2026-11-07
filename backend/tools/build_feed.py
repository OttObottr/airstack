# spec: AS-292
"""What changed, and what anyone may reuse: three public outputs built only from files the site already publishes (news.json,
events.json, profiles.json, chain-data.json and the product pages' slugs). No model call, no network, no database.

- changes.atom: an Atom 1.0 feed (RFC 4287) of the last 30 days: vendors' own changelogs, blogs and GitHub releases, Hacker News stories
  linking to a product's own site (news.json), and support cycles that ended (events.json, observed only: a scheduled or expected date
  is not a change). Each entry has a tag URI made from its source URL, the title as published, the source link and, when the product has
  one, its AirStack page as a related link. At most 200 entries, newest first; the feed is dated by its newest entry, never by the clock.
- badges.json: for each product with a profile, the numbers on its badge ("AirStack · N facts from its own pages · read <date>") and the
  one SVG template they fill.
- open-data/airstack-<YYYY-MM>.jsonl.gz: the month's release, one line per published fact, and open-data/README.md (licence, fields,
  releases). The month is the newest read date in the data.

A page withheld under AS-274 (airstack.fetch.published) appears in none of them, and is removed from earlier releases too.
The same inputs give the same bytes.

Usage: ../.venv/bin/python tools/build_feed.py"""
import gzip, json, re, sys, urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from airstack import paths

ROOT = paths.ROOT
from airstack.fetch import published
from pages.layout import slug as page_slug

BASE, ATOM, TAG = "https://airstack.bot", "http://www.w3.org/2005/Atom", "tag:airstack.bot,2026:"
DAYS, MAX_ENTRIES = 30, 200
SCHEDULE = "From {}’s support schedule on endoflife.date."
SAYS = {"changelog": "From {}’s own changelog.", "blog": "From {}’s own blog or news feed.", "release": "A GitHub release of {}.",
        "hacker news": "A Hacker News story linking to {}’s own site.", "end of life": SCHEDULE, "end of active support": SCHEDULE, "end of extended support": SCHEDULE}
NOT_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")
slug = lambda s: page_slug(s, 80)
tag = lambda url: TAG + urllib.parse.quote(url, safe="/:?@!$&'()*+,;=%-._~")      # RFC 4151: the source URL, percent-encoded where it must be

def rfc3339(d):
    t = datetime.fromisoformat(d.replace("Z", "+00:00"))
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------- changes.atom ----------
def changes(news, events, pages):
    """The feed's entries, newest first. `pages` maps a product id to its page slug (only products that have a page)."""
    end = date.fromisoformat(news["source"].get("read") or events["source"]["built_for"])
    start = (end - timedelta(days=DAYS)).isoformat()
    in_news = {i["url"] for i in news["items"]}
    rows = [(tag(i["url"]), i) for i in news["items"]]
    rows += [(tag(e["url"]) + "#" + slug(e["title"]), {**e, "date": e["at"]}) for e in events["events"]   # a support page lists many cycles
             if e["status"] == "observed" and e.get("url") and e["url"] not in in_news]
    out = {}
    for id_, i in rows:
        if id_ in out or not published(i["url"]) or not start < i["date"][:10] <= end.isoformat():
            continue
        out[id_] = {"id": id_, "title": NOT_XML.sub("", i["title"]).strip(), "link": i["url"], "updated": rfc3339(i["date"]), "name": i["name"],
                    "kind": i["kind"], "page": pages.get(i["id"]), "discussion": i.get("discussion")}
    return sorted(sorted(out.values(), key=lambda x: x["id"]), key=lambda x: x["updated"], reverse=True)[:MAX_ENTRIES]

def atom(entries, end):
    q = lambda t: f"{{{ATOM}}}{t}"
    def sub(parent, name, text=None, **attrs):
        el = ET.SubElement(parent, q(name), attrs)
        if text is not None: el.text = NOT_XML.sub("", text)
        return el
    ET.register_namespace("", ATOM)
    feed = ET.Element(q("feed"))
    sub(feed, "id", TAG + "changes"); sub(feed, "title", "AirStack: what changed")
    sub(feed, "subtitle", "Changelogs, releases and announcements from the products AirStack tracks, in the last 30 days, each linked to its source.")
    sub(feed, "link", rel="self", type="application/atom+xml", href=f"{BASE}/changes.atom"); sub(feed, "link", rel="alternate", type="text/html", href=f"{BASE}/")
    sub(feed, "updated", entries[0]["updated"] if entries else f"{end}T00:00:00Z")
    a = sub(feed, "author"); sub(a, "name", "AirStack"); sub(a, "uri", f"{BASE}/")
    sub(feed, "rights", "Titles remain their publishers' property. Original compilation metadata is CC BY 4.0 where applicable.")
    for x in entries:
        e = sub(feed, "entry")
        sub(e, "id", x["id"]); sub(e, "title", x["title"], type="text"); sub(e, "updated", x["updated"])
        sub(e, "link", rel="alternate", type="text/html", href=x["link"])
        if x["discussion"]: sub(e, "link", rel="replies", type="text/html", href=x["discussion"], title="Discussion on Hacker News")
        if x["page"]: sub(e, "link", rel="related", type="text/html", href=f"{BASE}/p/{x['page']}/", title=f"{x['name']} on AirStack")
        sub(e, "category", term=x["kind"]); sub(e, "summary", SAYS[x["kind"]].format(x["name"]) if x["kind"] in SAYS else f"{x['name']}: {x['kind']}.", type="text")
    ET.indent(feed)
    return ('<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(feed, encoding="unicode") + "\n").encode()

# ---------- badges.json ----------
FIELDS = ("count", "read", "tl", "w")                 # "12 facts", the newest read date, the text's length and the badge's width in px
LW, PAD, CHAR = 62, 7, 6.0                            # the label's width, the padding, an average glyph at 11px (textLength makes it exact)
TEMPLATE = ('<svg xmlns="http://www.w3.org/2000/svg" width="{{w}}" height="20" viewBox="0 0 {{w}} 20" role="img" '
            'aria-label="AirStack &#183; {{count}} from its own pages &#183; read {{read}}">'
            '<title>AirStack &#183; {{count}} from its own pages &#183; read {{read}}</title>'
            '<style>.f{fill:#ECECEF}.t{fill:#0A0A0B}@media (prefers-color-scheme:dark){.f{fill:#232326}.t{fill:#F5F5F7}}</style>'
            '<rect class="f" width="100%" height="20" rx="3"/>'
            f'<rect width="{LW}" height="20" rx="3" fill="#FF4F00"/><rect x="{LW - 3}" width="3" height="20" fill="#FF4F00"/>'
            '<g font-family="system-ui,-apple-system,Segoe UI,Helvetica,Arial,sans-serif" font-size="11">'
            f'<text x="{PAD}" y="14" fill="#0A0A0B" font-weight="600" textLength="{LW - 2 * PAD}" lengthAdjust="spacingAndGlyphs">AirStack</text>'
            f'<text class="t" x="{LW + PAD}" y="14" textLength="{{{{tl}}}}" lengthAdjust="spacingAndGlyphs">{{{{count}}}} from its own pages &#183; read {{{{read}}}}</text>'
            '</g></svg>')

def badges(profiles, slugs):
    """{slug: row} for every profiled product; `slugs` maps a product id to its page slug."""
    out = {}
    for pid, p in profiles.items():
        read = max(c.get("checked", "") for c in p.values() if isinstance(c, dict))
        count = f"{p['facts']} fact{'' if p['facts'] == 1 else 's'}"
        tl = round(len(f"{count} from its own pages · read {read}") * CHAR)
        out[slugs[pid]] = [count, read, tl, LW + PAD + tl + PAD]
    return {"fields": list(FIELDS), "template": TEMPLATE, "badges": out}

def badge_svg(data, s):
    """The badge for one slug: each {{field}} in the template replaced by the row's value."""
    row = data["badges"][s]
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(row[data["fields"].index(m[1])]), data["template"])

# ---------- open data ----------
OPEN_FIELDS = ("id", "name", "metric", "value", "quote", "url", "read", "licence")
WIKIMEDIA = re.compile(r"(^|\.)(wikipedia|wikimedia|wikibooks|wikiversity|wikiquote|wiktionary|wikisource|wikinews|wikivoyage|mediawiki)\.org$")
LICENCE = "Original record metadata: CC BY 4.0 where applicable. Quote: publisher's words, linked to source."
LICENCE_WIKIMEDIA = "Original record metadata: CC BY 4.0 where applicable. Quote: CC BY-SA 4.0, linked to Wikimedia source."

def open_lines(chain):
    """One JSON line per published fact in chain-data.json: the quote, never the page."""
    rows = {json.dumps({"id": pid, "name": e["name"], "metric": f["metric"], "value": f["value"], "quote": f["quote"], "url": f["url"], "read": f["retrieved"],
                        "licence": LICENCE_WIKIMEDIA if WIKIMEDIA.search(f["host"]) else LICENCE}, ensure_ascii=False, sort_keys=True)
            for pid, e in chain["entities"].items() for f in e["facts"] if published(f["url"])}
    return sorted(rows)

def pack(lines):
    return gzip.compress("".join(l + "\n" for l in lines).encode(), mtime=0)

def unpack(blob):
    return gzip.decompress(blob).decode().splitlines()

def same(name, blob, old):
    """Whether an output is unchanged. A release compares by its text: another zlib may compress the same lines to other bytes."""
    return old == blob or (name.endswith(".gz") and unpack(old) == unpack(blob))

def readme(releases):
    rows, prev = [], set()
    for name, lines in sorted(releases.items()):
        now = set(lines)
        rows.append(f"| `{name}` | {len(now):,} | {len({json.loads(l)['id'] for l in now}):,} | {len(now - prev):,} | {len(prev - now):,} |")
        prev = now
    return """# AirStack open data

The facts AirStack has read on products' own pages, one JSON line per fact, released each month as `airstack-<YYYY-MM>.jsonl.gz`. Each
fact is a short quote from the page, with the link and the day the page was read, so anyone can check it.

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
| `metric` | What the fact is about, such as `what_it_does`, `platforms`, `integrations`, `compliance` or `free_plan` |
| `value` | The value read from the quote: text, a list, true or false, or a number |
| `quote` | The page's own words, at most 25 words |
| `url` | The page the quote is on |
| `read` | The day AirStack read that page (YYYY-MM-DD) |
| `licence` | The licence note for this line |

Left out: the stored page text, prices, and every fact from a page whose terms bar automated reading or whose robots.txt is closed to
AirStackBot. A page that closes later is removed from earlier releases too.

## How it is built

`backend/tools/build_feed.py` reads `chain-data.json`, the evidence file the site serves, and writes this month's release and this file.
It makes no model call and no network request, and the same input gives the same bytes. The release for a month is the last build in it.

## Releases

| Release | Facts | Products | New since the previous release | Gone since the previous release |
|---|---|---|---|---|
""" + "\n".join(rows) + "\n"

# ---------- build ----------
def read_json(name):
    return json.loads((paths.SITE / name).read_text())

def build():
    """Every output as {path relative to the repository: bytes}. Reads only files the site already serves."""
    import build_pages
    all_ = build_pages.products()
    pages = {k: p["slug"] for k, p in build_pages.built(all_, build_pages.own_prices(all_, read_json("pricing.json") if paths.PRICING.exists() else {})).items()}
    news, events = read_json("news.json"), read_json("events.json")
    out = {"changes.atom": atom(changes(news, events, pages), news["source"].get("read") or events["source"]["built_for"]),
           "badges.json": json.dumps(badges(read_json("profiles.json"), {k: p["slug"] for k, p in all_.items()}), ensure_ascii=False,
                                     sort_keys=True, separators=(",", ":")).encode() + b"\n"}
    lines = open_lines(read_json("chain-data.json"))
    releases = {f.name: [l for l in unpack(f.read_bytes()) if published(json.loads(l)["url"])] for f in sorted(paths.OPEN_DATA.glob("airstack-*.jsonl.gz"))}
    releases[f"airstack-{max(json.loads(l)['read'] for l in lines)[:7]}.jsonl.gz"] = lines       # this month's release; earlier ones lose withheld pages
    out |= {f"open-data/{name}": pack(ls) for name, ls in releases.items()}
    out["open-data/README.md"] = readme(releases).encode()
    return out

def main():
    out = build()
    for name, blob in out.items():
        p = paths.SITE / name; p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists() or not same(name, blob, p.read_bytes()):
            p.write_bytes(blob)
    n = len(ET.fromstring(out["changes.atom"]).findall(f"{{{ATOM}}}entry"))
    print(f"changes.atom: {n} entries; badges.json: {len(json.loads(out['badges.json'])['badges'])} badges; "
          + "; ".join(f"{k}: {len(unpack(v)):,} facts" for k, v in out.items() if k.endswith(".jsonl.gz")))

if __name__ == "__main__":
    sys.exit(main())
