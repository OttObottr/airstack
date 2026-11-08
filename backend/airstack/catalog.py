"""Cataloged products: a name, a category and checked links, nothing else claimed."""
from . import paths
from .files import read_json

PATH = paths.CATALOG

CATEGORIES = paths.config("categories")["categories"]


def entries(path=PATH):
    """Entries whose homepage was reachable at the last check, in catalog order."""
    if not path.exists():
        return []
    return [e for e in read_json(path) if (e.get("checked") or {}).get("reachable") in ("yes", "blocked by the site's bot protection")]


def public(e):
    """What a page or an agent may show about a cataloged product."""
    ck = e.get("checked") or {}
    return {"id": e["id"], "name": e["name"], "category": e["category"], "category_name": CATEGORIES[e["category"]], "vendor": e.get("vendor"),
            "homepage": e["homepage"], "pricing": e.get("pricing"), "domain": e.get("domain"), "aliases": e.get("aliases") or [], "checked": ck.get("date")}
