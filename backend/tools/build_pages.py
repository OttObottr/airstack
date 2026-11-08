"""The crawlable pages (product, maker, category, comparison, taxonomy, reports) and sitemap.xml.
Usage: python backend/tools/build_pages.py"""
import shutil
import sys
from airstack import paths
from pages.data import DIRECTORY, built, own_prices, products
from pages.layout import BASE
from pages.category import cat_pages
from pages.comparison import compare_pages
from pages.organization import org_pages
from pages.product import page, product_directory
from pages.report import report_pages
from pages.taxonomy import taxonomy_pages
from airstack.files import read_json


def main():
    DIRECTORY.update(read_json(paths.DIRECTORY))
    all_ = products(); prices = read_json(paths.PRICING) if paths.PRICING.exists() else {}
    prices = own_prices(all_, prices)
    oss = read_json(paths.OSS) if paths.OSS.exists() else {}
    for p in all_.values():
        p["page"] = p["id"] in built(all_, prices)
    org_urls = org_pages(all_)
    cat_urls = cat_pages(all_, prices, oss)  # hubs first: product pages link up to them
    tax_urls = taxonomy_pages(all_)
    cmp_urls = compare_pages(all_, prices)  # pairs within one software type
    shutil.rmtree(paths.PAGE_DIRS["p"], ignore_errors=True); n = 0; urls = []
    for p in sorted(all_.values(), key=lambda x: x["slug"]):
        if not p["page"]:
            continue
        d = paths.PAGE_DIRS["p"] / p["slug"]; d.mkdir(parents=True, exist_ok=True); (d / "index.html").write_text(page(p, all_, prices, oss)); n += 1
        urls.append(f"{BASE}/p/{p['slug']}/")
    product_urls = product_directory(all_)
    report_urls = report_pages()
    sitemap = [f"{BASE}/", f"{BASE}/open-data/"] + report_urls + product_urls + cat_urls + cmp_urls + tax_urls + urls + org_urls
    paths.SITEMAP.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{url}</loc></url>\n" for url in sitemap) + "</urlset>\n")
    print(f"c/: {len(cat_urls)} category pages, compare/: {len(cmp_urls)}, t/: {len(tax_urls)}, p/: {n} product pages + {len(product_urls)} directories, o/: {len(org_urls)} organization pages, reports: {len(report_urls)}, "
          f"sitemap.xml: {len(sitemap)} URLs")

if __name__ == "__main__":
    sys.exit(main())
