"""What every page type shares: the products with a page, the config they read, and registries filled by build_pages.main."""
import collections
import re
from airstack import paths
from .layout import WIKIMEDIA, e, slug
from airstack.evidence import report_url, shown, text_fragment
from airstack.quotes import norm
from airstack.files import read_json

PAGES, PRICING = paths.config("pages"), paths.config("pricing")

_CHAIN = read_json(paths.CHAIN_DATA) if paths.CHAIN_DATA.exists() else {}
CHAIN, POLICY = _CHAIN.get("entities", {}), _CHAIN.get("policy", {"tiers": {"high": [], "medium": [], "low": []}})

HOSTS = set(PRICING["shared_hosts"])                                                   # many products' pages, nobody's prices

LABELS = [(k, label) for k, label in PAGES["labels"] if shown(POLICY, k)]   # the published policy decides what is shown

def site(u):
    h = re.sub(r"^www\.", "", (re.match(r"https?://([^/:]+)", u or "") or [None, ""])[1].lower()); parts = h.split(".")
    return h if h in HOSTS else ".".join(parts[-3:] if len(parts) > 2 and parts[-2] in ("co", "com", "org", "net", "ac") else parts[-2:])

def products():
    """Every product the app can show with something to say: tracked tools, catalog products, and researched directory listings."""
    site = paths.read_js(paths.SITE_DATA); profiles = read_json(paths.PROFILES)
    cats = {c["id"]: c["name"] for c in site.get("cats", [])} | {ln["id"]: ln["name"] for ln in site["lanes"]}
    catalog = {e_["id"]: e_ for e_ in read_json(paths.CATALOG)}
    trust = {e_["id"]: (e_.get("pages") or {}).get("security") for e_ in [*read_json(paths.UNIVERSE), *catalog.values()]}
    out = {}
    for row in site["index"]:
        pid, name, lane = row[0], row[1], row[2]
        c = catalog.get(pid, {})
        out[pid] = {"id": pid, "name": name, "slug": slug(pid), "lane": lane, "category": cats.get(lane, lane), "homepage": c.get("homepage"),
                    "vendor": c.get("vendor"), "profile": profiles.get(pid), "catalog": pid in catalog,
                    "trust": trust.get(pid)}
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

day = lambda d: f'<time datetime="{e(d)}">{e(d)}</time>'

def says(p, f):
    """Whose words a quote is: the vendor's own page, or the store or platform page it came from."""
    return f"{e(p['name'])}’s page" if f.get("class") == "vendor" else e(f["host"])

def checks(p, label, f):
    """How to check one fact: the quote highlighted on its page, an archived copy, its dates and a prefilled problem report."""
    when = " · ".join(x for x in (f"first read {day(f['first_read'])}" if f.get("first_read") else "", f"re-checked {day(f['checked'])}" if f.get("checked") else "") if x)
    archived = f' · <a href="{e(f["archived"]["url"])}" rel="nofollow noopener">Archived copy</a>' if f.get("archived") else ""
    licence = ' · quote <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>' if WIKIMEDIA.search(f["host"]) else ""
    return (f'<a href="{e(text_fragment(f["url"], f["quote"]))}" rel="nofollow noopener">See it on {e(f["host"])}</a>{archived} · {when}{licence}'
            f' · <a href="{e(report_url(p["name"], label, f["url"], f["quote"]))}" rel="nofollow noopener">Report a problem</a>')

def fact_cell(p, metric, label, claim, most=None):
    """The value, then each supporting quote attributed to the page it came from, with the links and dates to check it.
    Where the value is the quote itself, only the attributed quote is shown."""
    facts = evidence(p["id"], metric, claim)[:most]
    if not facts:
        return e(value(claim)) + " ".join(f'<br><small><a href="{e(s["url"])}" rel="nofollow noopener">{e(s["host"])}</a></small>' for s in claim.get("sources", [])[:2])
    own = len(facts) == 1 and norm(facts[0]["quote"]) == norm(value(claim))
    return ("" if own else e(value(claim)) + "<br>") + "<br>".join(f'<small>{says(p, f)} says: <q>{e(f["quote"])}</q><br>{checks(p, label, f)}</small>' for f in facts)

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

def listed(q):
    """A pricing page's plans as it lists them, with the day they were read: never a total, a cheapest or a comparison."""
    return (f'<a href="{e(q["url"])}" rel="nofollow noopener">{e(re.sub(r"^https?://(www[.])?", "", q["url"]).split("/")[0])}</a> lists '
            f'{len(q["plans"])} plan{"s" if len(q["plans"]) != 1 else ""}. Listed on {day(q["checked"])}') if q and q.get("plans") else ""

DIRECTORY = {}

ORGS = {}  # Wikidata id -> maker page slug

CATS = set()  # categories with a page

PAIRS = {}  # product id -> [(other id, compare slug)]

TAXON = {}  # product id -> taxonomy node id

NODES = {}  # node id -> its taxonomy record

kids_members = {}  # node id -> products placed in it or below
