# spec: AS-252 AS-257 AS-285 AS-316 AS-317 AS-318 AS-319
"""A static, crawlable page per product (/p/<slug>/): what search engines and AI answer engines can read and cite, built from the same
generated files the app uses (profiles.json, pricing.json, oss.json, the catalog and the directory). Each page carries a title, a
description, a canonical URL, Open Graph tags and JSON-LD (SoftwareApplication; offers only from sourced list prices), and the facts with
their sources in plain HTML. Also writes sitemap.xml. No model call.

One module per page type in backend/tools/pages/ (product, organization, makers, category, comparison, taxonomy); layout.py owns the
<head>, stylesheet and footer they share, data.py the products and the config they read. This file is the entry point.

Usage: ../.venv/bin/python tools/build_pages.py"""
import json, shutil, sys
from airstack import paths
from pages.data import DIRECTORY, built, own_prices, products
from pages.data import ADDON, HOSTS, site                                       # noqa: F401  (read by the tests)
from pages.layout import BASE
from pages.category import cat_pages
from pages.comparison import SHARED, compare_pages                             # noqa: F401  (SHARED is read by the tests)
from pages.organization import org_pages
from pages.product import page
from pages.taxonomy import taxonomy_pages


def main():
    DIRECTORY.update(json.loads(paths.DIRECTORY.read_text()))
    all_ = products(); prices = json.loads(paths.PRICING.read_text()) if paths.PRICING.exists() else {}
    prices = own_prices(all_, prices)
    oss = json.loads(paths.OSS.read_text()) if paths.OSS.exists() else {}
    for p in all_.values():
        p["page"] = p["id"] in built(all_, prices)
    org_urls = org_pages(all_)
    cat_urls = cat_pages(all_, prices, oss)                                    # before the product pages, so their breadcrumbs can link up
    cmp_urls = compare_pages(all_, prices)                                    # and so each product page can link its comparisons
    tax_urls = taxonomy_pages(all_)                                           # and its place in the software taxonomy
    shutil.rmtree(paths.PAGE_DIRS["p"], ignore_errors=True); n = 0; urls = []
    for p in sorted(all_.values(), key=lambda x: x["slug"]):
        if not p["page"]:
            continue
        d = paths.PAGE_DIRS["p"] / p["slug"]; d.mkdir(parents=True, exist_ok=True); (d / "index.html").write_text(page(p, all_, prices, oss)); n += 1
        checked = max([c.get("checked", "") for c in (p["profile"] or {}).values() if isinstance(c, dict)] + ["2026-11-04"])
        urls.append((f"{BASE}/p/{p['slug']}/", checked[:10]))
    paths.SITEMAP.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{BASE}/</loc><lastmod>2026-11-05</lastmod></url>\n" + "".join(f"  <url><loc>{u}</loc><lastmod>{m}</lastmod></url>\n" for u, m in cat_urls + cmp_urls + tax_urls + urls + org_urls) + "</urlset>\n")
    print(f"c/: {len(cat_urls)} category pages, compare/: {len(cmp_urls)}, t/: {len(tax_urls)}, p/: {n} product pages, o/: {len(org_urls)} organization pages, "
          f"sitemap.xml: {len(cat_urls) + len(cmp_urls) + len(tax_urls) + n + len(org_urls) + 1} URLs")

if __name__ == "__main__":
    sys.exit(main())
