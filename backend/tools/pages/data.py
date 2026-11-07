# spec: AS-252 AS-257 AS-285 AS-316 AS-317 AS-318 AS-319
"""Shared by every page type: the products that get a page, their sourced prices, the constants read from config/, and the registries a page type fills before another reads them (set by build_pages.main)."""
import collections, json, re
from airstack import paths
from airstack.publication import public_prices
from .layout import slug

PAGES, PRICING = paths.config("pages"), paths.config("pricing")         # config/pages.json, config/pricing.json

HOSTS = set(PRICING["shared_hosts"])                                                   # many products' pages, nobody's prices

ADDON = re.compile(PRICING["addon_pattern"], re.I)

LABELS = PAGES["labels"]

CURRENCY = PAGES["currency"]

def site(u):
    h = re.sub(r"^www\.", "", (re.match(r"https?://([^/:]+)", u or "") or [None, ""])[1].lower()); parts = h.split(".")
    return h if h in HOSTS else ".".join(parts[-3:] if len(parts) > 2 and parts[-2] in ("co", "com", "org", "net", "ac") else parts[-2:])

def plan_ok(q):
    """A plan that can stand for what a product costs: a stated unit and period, not an add-on, credit or usage line."""
    return q["unit"] in ("user", "flat") and q["period"] in ("month", "year") and not ADDON.search(q["plan"] + " " + q.get("quote", "")) and re.search(r"[1-9]", q["price"])

def products():
    """Every product the app can show with something to say: tracked tools, catalog products, and researched directory listings."""
    site = paths.read_js(paths.SITE_DATA); profiles = json.loads(paths.PROFILES.read_text())
    cats = {c["id"]: c["name"] for c in site.get("cats", [])} | {l["id"]: l["name"] for l in site["lanes"]}
    catalog = {e_["id"]: e_ for e_ in json.loads(paths.CATALOG.read_text())}
    out = {}
    for row in site["index"]:
        pid, name, lane = row[0], row[1], row[2]
        c = catalog.get(pid, {})
        out[pid] = {"id": pid, "name": name, "slug": slug(pid), "lane": lane, "category": cats.get(lane, lane), "homepage": c.get("homepage"),
                    "vendor": c.get("vendor"), "profile": profiles.get(pid), "catalog": pid in catalog}
    d = json.loads(paths.DIRECTORY.read_text()); T = d["types"]
    used = {v["slug"] for v in out.values()}
    for pid, name, desc, site_url, t, makers, links, _ in d["products"]:
        if pid in profiles and pid not in out:
            s = slug(name)
            if s in used:
                s = f"{s}-{pid.lower()}"                                     # a readable address; the id only where two names read the same
            used.add(s)
            out[pid] = {"id": pid, "name": name, "slug": s, "lane": "directory", "category": T[t][1][:1].upper() + T[t][1][1:], "homepage": site_url,
                        "vendor": ", ".join(d["orgs"][m][0] for m in makers if m in d["orgs"]) or None, "makers": [m for m in makers if m in d["orgs"]],
                        "profile": profiles[pid], "catalog": False, "wikidata": pid,
                        "description": desc}
    return out

def own_prices(all_, prices):
    """The same attributed, current public price projection used by MCP, insights, stats and counts."""
    return {pid: q for pid, q in public_prices(prices).items() if pid in all_}

def built(all_, prices):
    """The products that get a page: researched, cataloged, or with a sourced list price."""
    return {k: p for k, p in all_.items() if p["profile"] or p["catalog"] or prices.get(k)}

def app_addr(pid, name):
    """How the app addresses a listing in a link: its name where that is unique among the directory's products and organizations, else its id (the app resolves both)."""
    global _NAMES
    if _NAMES is None:
        _NAMES = collections.Counter([slug(p[1]) for p in DIRECTORY["products"]] + [slug(o[0]) for o in DIRECTORY["orgs"].values() if o[5] != "person"])
    return slug(name) if pid.startswith("Q") and _NAMES[slug(name)] == 1 else pid

_NAMES = None

def value(c):
    v = c["value"]
    return "Yes" if v is True else ", ".join(map(str, v)) if isinstance(v, list) else str(v)

def amount(price):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", price or ""); return float(m.group(0).replace(",", "")) if m else None

def starting(q):
    """The cheapest paid plan as written on the pricing page, and whether a free plan is listed: only sourced list prices."""
    plans = (q or {}).get("plans", [])
    paid = sorted((pl for pl in plans if plan_ok(pl) and re.search(r"[$€£¥]", pl["price"])), key=lambda pl: amount(pl["price"]))
    return (paid[0] if paid else None), any(amount(pl["price"]) == 0 for pl in plans)

DIRECTORY = {}

ORGS = {}                                                                        # Wikidata id -> organization page slug, set by main() before any page is written

CATS = set()                                                                     # categories that have a page, set by main()

PAIRS = {}                                                                       # product id -> [(other id, compare slug)], set by main()

TAXON = {}                                                                       # product id -> its taxonomy node id, set by taxonomy_pages() before any product page is written

NODES = {}                                                                       # node id -> its record in data/taxonomy.json

kids_members = {}                                                                # node id -> every product placed in it or below it
