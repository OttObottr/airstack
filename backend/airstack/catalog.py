# spec: AS-237
"""The mainstream catalog (data/catalog.json): paid products people renew, each listed under one category, each homepage,
pricing, docs, integrations and security URL checked live by tools/check_catalog.py. An entry is "cataloged" until its own
pages are researched: its name, category and links are known, nothing else is claimed about it."""
import json
from . import paths

PATH = paths.CATALOG

CATEGORIES = paths.config("categories")["categories"]                      # config/categories.json


def entries(path=PATH):
    """Every entry whose homepage was reached when it was last checked, in catalog order. No file: no entries."""
    if not path.exists():
        return []
    return [e for e in json.loads(path.read_text()) if (e.get("checked") or {}).get("reachable") in ("yes", "blocked by the site's bot protection")]


def public(e):
    """What a page or an agent may show about a cataloged product: identity, category and the links we checked."""
    ck = e.get("checked") or {}
    return {"id": e["id"], "name": e["name"], "category": e["category"], "category_name": CATEGORIES[e["category"]], "vendor": e.get("vendor"),
            "homepage": e["homepage"], "pricing": e.get("pricing"), "domain": e.get("domain"), "aliases": e.get("aliases") or [], "checked": ck.get("date")}
