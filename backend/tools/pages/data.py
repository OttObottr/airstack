"""What every page type shares: the products with a page, the config they read, and registries filled by build_pages.main."""
import collections
import re
from airstack import paths
from .layout import WIKIMEDIA, e, slug
from airstack.quotes import norm
from airstack.files import read_json

PAGES, PRICING = paths.config("pages"), paths.config("pricing")

CHAIN = read_json(paths.CHAIN_DATA)["entities"] if paths.CHAIN_DATA.exists() else {}

HOSTS = set(PRICING["shared_hosts"])                                                   # many products' pages, nobody's prices

ADDON = re.compile(PRICING["addon_pattern"], re.I)

LABELS = PAGES["labels"]


def site(u):
    h = re.sub(r"^www\.", "", (re.match(r"https?://([^/:]+)", u or "") or [None, ""])[1].lower()); parts = h.split(".")
    return h if h in HOSTS else ".".join(parts[-3:] if len(parts) > 2 and parts[-2] in ("co", "com", "org", "net", "ac") else parts[-2:])

def plan_ok(q):
    """A plan that can stand for what a product costs: a stated unit and period, not an add-on, credit or usage line."""
    return q["unit"] in ("user", "flat") and q["period"] in ("month", "year") and not ADDON.search(q["plan"] + " " + q.get("quote", "")) and (q.get("amount") or 0) > 0

def products():
    """Every product the app can show with something to say: tracked tools, catalog products, and researched directory listings."""
    site = paths.read_js(paths.SITE_DATA); profiles = read_json(paths.PROFILES)
    cats = {c["id"]: c["name"] for c in site.get("cats", [])} | {ln["id"]: ln["name"] for ln in site["lanes"]}
    catalog = {e_["id"]: e_ for e_ in read_json(paths.CATALOG)}
    out = {}
    for row in site["index"]:
        pid, name, lane = row[0], row[1], row[2]
        c = catalog.get(pid, {})
        out[pid] = {"id": pid, "name": name, "slug": slug(pid), "lane": lane, "category": cats.get(lane, lane), "homepage": c.get("homepage"),
                    "vendor": c.get("vendor"), "profile": profiles.get(pid), "catalog": pid in catalog}
    d = read_json(paths.DIRECTORY); T = d["types"]
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

def found(v, of):
    """A category count as "N found of M": a {found, of} record, or a bare count out of the products read."""
    k, m = (v["found"], v["of"]) if isinstance(v, dict) else (v, of)
    return f"{k:,} found of {m:,}"

def own_prices(all_, prices):
    return {pid: q for pid, q in prices.items() if pid in all_}

def built(all_, prices):
    """The products that get an indexable page: researched or carrying a sourced list price."""
    return {k: p for k, p in all_.items() if p["profile"] or prices.get(k)}


def evidence(pid, metric, claim):
    """The source quotes behind one normalized profile field, matched by metric and source URL: one per listed value."""
    urls = {s["url"] for s in claim.get("sources", [])}
    facts = [f for f in CHAIN.get(pid, {}).get("facts", []) if f["metric"] == metric and f["url"] in urls and f.get("quote")]
    items = lambda v: list(dict.fromkeys(norm(str(x)) for x in (v if isinstance(v, list) else [v])))
    out = []
    for v in items(claim["value"]):
        f = next((f for f in facts if v in items(f["value"])), None)
        if f and f not in out:
            out.append(f)
    return out or facts[:1]

def proof(pid, metric, claim):
    """Each supporting quote with its page and read date; the quote is left out where it is the value itself."""
    shown = norm(value(claim))
    def one(f):
        q = "" if norm(f["quote"]) == shown else f"<q>{e(f['quote'])}</q> — "
        licence = ' · quote <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>' if WIKIMEDIA.search(f["host"]) else ""
        return f'{q}<cite><a href="{e(f["url"])}" rel="nofollow noopener">{e(f["host"])}</a>, read <time datetime="{e(f["retrieved"][:10])}">{e(f["retrieved"][:10])}</time>{licence}</cite>'
    facts = evidence(pid, metric, claim)
    src = "<br>".join(map(one, facts)) if facts else " ".join(f'<a href="{e(s["url"])}" rel="nofollow noopener">{e(s["host"])}</a>' for s in claim.get("sources", [])[:2])
    return f"<br><small>{src}</small>"

def app_addr(pid, name):
    """How the app links a listing: its name where unique among listings and makers, else its id."""
    global _NAMES
    if _NAMES is None:
        _NAMES = collections.Counter([slug(p[1]) for p in DIRECTORY["products"]] + [slug(o[0]) for o in DIRECTORY["orgs"].values() if o[5] != "person"])
    return slug(name) if pid.startswith("Q") and _NAMES[slug(name)] == 1 else pid

_NAMES = None

def value(c):
    v = c["value"]
    return "Yes" if v is True else ", ".join(map(str, v)) if isinstance(v, list) else str(v)

def starting(q):
    """The cheapest paid plan as written on the pricing page, and whether a free plan is listed: only sourced list prices."""
    plans = (q or {}).get("plans", [])
    paid = sorted((pl for pl in plans if plan_ok(pl) and pl.get("currency")), key=lambda pl: pl["amount"])
    return (paid[0] if paid else None), any(pl.get("amount") == 0 for pl in plans)

DIRECTORY = {}

ORGS = {}  # Wikidata id -> maker page slug

CATS = set()  # categories with a page

PAIRS = {}  # product id -> [(other id, compare slug)]

TAXON = {}  # product id -> taxonomy node id

NODES = {}  # node id -> its taxonomy record

kids_members = {}  # node id -> products placed in it or below
