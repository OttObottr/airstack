"""The one <head>, stylesheet and footer every generated page shares."""
import html
import json
import re

BASE = "https://airstack.bot"
WIKIMEDIA = re.compile(r"(^|\.)(wikipedia|wikimedia|wikibooks|wikiversity|wikiquote|wiktionary|wikisource|wikinews|wikivoyage|mediawiki)\.org$")
STYLE = '<style>:root{color-scheme:dark}body{margin:0;background:#0A0A0B;color:#F5F5F7;font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:880px;margin:0 auto;padding:32px 20px 64px}\na{color:#F5F5F7;text-decoration-color:rgba(255,255,255,.3);text-underline-offset:3px}nav{font-size:14px;color:rgba(245,245,247,.66)}nav a{color:inherit}h1{font-size:clamp(32px,6vw,48px);letter-spacing:-.03em;line-height:1.05;margin:16px 0 8px}\nh2{font-size:20px;margin:40px 0 12px}.lead{font-size:19px;color:rgba(245,245,247,.82)}.cta{display:inline-block;margin-top:20px;padding:12px 20px;border-radius:999px;background:#FF4F00;color:#0A0A0B;font-weight:600;text-decoration:none}\ntable{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;overflow-wrap:anywhere;padding:10px 8px;border-top:1px solid rgba(255,255,255,.12)}th{width:34%;font-weight:500;color:rgba(245,245,247,.66)}small{color:rgba(245,245,247,.66)}\nul{padding-left:20px}li{margin:6px 0}footer{margin-top:48px;font-size:13px;color:rgba(245,245,247,.66)}</style>\n'

e = lambda s: html.escape(str(s), quote=True)

foot = lambda extra="": ("<footer>AirStack: every claim about software, with the page it came from. " + extra +
                         'Browse <a href="/p/">products</a>, <a href="/c/">categories</a>, <a href="/t/">software types</a>, and <a href="/o/">makers</a>. <a href="/insights/">Insights</a>. <a href="/calendar/">Calendar</a>. <a href="/method/">Method</a>. <a href="/open-data/">Open data</a>. '
                         "Original compilation metadata is CC BY 4.0 where applicable; third-party material remains its owners’ property. "
                         '<a href="/legal/">Terms, privacy and sources</a>. <a href="https://github.com/OttObottr/airstack">Source</a></footer>')

slug = lambda s, n=60: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n] or "x"

def trim(t, n=140):
    t = str(t); return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",;:-") + "…"


def breadcrumbs(items):
    """One visible breadcrumb and its matching structured data. The final item has no link."""
    nav = " › ".join(f'<a href="{e(url)}">{e(name)}</a>' if url else e(name) for name, url in items)
    rows = []
    for position, (name, url) in enumerate(items, 1):
        row = {"@type": "ListItem", "position": position, "name": name}
        if url: row["item"] = url if url.startswith("http") else BASE + url
        rows.append(row)
    return f'<nav aria-label="Breadcrumb">{nav}</nav>', {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": rows}


def head(title, desc, url, lds, og_title=None):
    """The <head> every page shares: title, description, canonical URL, Open Graph and Twitter tags, the JSON-LD blocks and the stylesheet."""
    d = e(desc[:300])
    blocks = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False).replace("<", "\\u003c")}</script>' for x in lds)
    return (f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{d}"><link rel="canonical" href="{url}">
<meta property="og:type" content="website"><meta property="og:site_name" content="AirStack"><meta property="og:title" content="{e(og_title or title)}"><meta property="og:description" content="{d}"><meta property="og:url" content="{url}"><meta property="og:image" content="{BASE}/icons/og.png"><meta property="og:image:alt" content="AirStack software market intelligence">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{e(og_title or title)}"><meta name="twitter:description" content="{d}"><meta name="twitter:image" content="{BASE}/icons/og.png"><link rel="alternate" type="application/atom+xml" href="/changes.atom"><link rel="icon" href="/icons/icon-192.png">
{blocks}
{STYLE}</head>
''')
