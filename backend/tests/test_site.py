"""The static site and its rendered pages: honest structured data, shipped assets, safe headers, and only sourced prices."""
from conftest import ROOT
import functools
import html
import json
import re
import struct
import xml.etree.ElementTree as ET
from airstack import paths


WEB = [ROOT / "web" / "index.html", *sorted((ROOT / "web" / "src").rglob("*.js")), *sorted((ROOT / "web" / "src").rglob("*.css"))]

INDEX = "\n".join(p.read_text() for p in WEB)

def test_structured_data_says_only_what_the_page_says():
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', INDEX, re.S).group(1))
    desc = html.unescape(re.search(r'<meta name="description" content="([^"]+)"', INDEX).group(1))
    assert {n["@type"] for n in ld["@graph"]} == {"WebSite", "SoftwareApplication"}
    assert all(n["description"] == desc for n in ld["@graph"])

def test_crawl_and_install_files_exist_and_point_at_airstack_bot():
    for f in ("robots.txt", "llms.txt", "manifest.webmanifest", "sw.js"):
        assert (ROOT / "web" / "public" / f).exists(), f
    assert paths.SITEMAP.exists()
    assert "Sitemap: https://airstack.bot/sitemap.xml" in (ROOT / "web" / "public" / "robots.txt").read_text()
    assert "<loc>https://airstack.bot/</loc>" in paths.SITEMAP.read_text()
    m = json.loads((ROOT / "web" / "public" / "manifest.webmanifest").read_text())
    assert {i["sizes"] for i in m["icons"]} >= {"192x192", "512x512"} and any(i.get("purpose") == "maskable" for i in m["icons"])
    assert all((ROOT / "web" / "public" / i["src"]).exists() for i in m["icons"])

def test_deploy_ships_every_local_file_the_page_loads():
    assemble = (ROOT / "tools" / "assemble.sh").read_text()
    shipped = {f.split("/")[-1] for line in re.findall(r'^cp (?:-R )?(.+?) "\$out"/$', assemble, re.M) for f in line.split()}
    shipped |= {f.name for f in (ROOT / "web" / "public").iterdir()} | {f.name for f in paths.SITE.iterdir()}
    refs = set(re.findall(r'(?:href|src)="(?![a-z][\w+.-]*:|#|\$\{)([^"]+)"', INDEX)) | {"sw.js", "manifest.webmanifest"} | set(re.findall(r"fetch\('([\w./-]+)'", INDEX))
    refs = {r.lstrip("/") for r in refs}
    assert {"src/main.js", "src/styles/index.css"} <= refs and '(web / "src").rglob("*.js")' in assemble
    refs = {r for r in refs if not (r.startswith("src/") and (ROOT / "web" / r).is_file())}
    refs |= {i["src"] for i in json.loads((ROOT / "web" / "public" / "manifest.webmanifest").read_text())["icons"]}
    refs |= set(re.findall(r"'([\w./-]+\.(?:html|js|webmanifest|woff2|png))'", (ROOT / "web" / "public" / "sw.js").read_text())) - {"./"}
    missing = [r for r in refs if r not in shipped and r.split("/")[0] not in shipped]
    assert not missing, missing

def test_share_card_exists_and_is_the_size_its_tags_promise():
    ref = re.search(r'og:image" content="https://airstack\.bot/([^"]+)"', INDEX).group(1)
    png = (ROOT / "web" / "public" / ref).read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", png[16:24]) == (1200, 630) and len(png) < 150_000
    assert 'name="twitter:card" content="summary_large_image"' in INDEX and 'og:image:width" content="1200"' in INDEX

def test_security_headers_are_on_every_response():
    star = re.search(r"(?m)^/\*\n((?:[ \t]+.+\n?)+)", (ROOT / "web" / "public" / "_headers").read_text()).group(1)
    hdr = {k.strip().lower(): v.strip() for k, v in (ln.split(":", 1) for ln in star.splitlines() if ln.strip())}
    assert hdr["strict-transport-security"].startswith("max-age=") and "includesubdomains" not in hdr["strict-transport-security"].lower()
    assert hdr["x-frame-options"] == "DENY" and hdr["x-content-type-options"] == "nosniff"
    csp = {d.split()[0]: d.split()[1:] for d in hdr["content-security-policy"].split("; ")}
    assert csp["default-src"] == ["'self'"] and csp["object-src"] == ["'none'"] and csp["base-uri"] == ["'none'"] and csp["frame-ancestors"] == ["'none'"]
    assert all("http" not in v and "*" not in v for vals in csp.values() for v in vals)
    assert '"workers_dev": false' in (ROOT / "wrangler.jsonc").read_text()

def test_every_scraped_url_goes_through_the_scheme_check():
    assert re.search(r"const url\s*=\s*u\s*=>", INDEX) and 'href="${esc(' not in INDEX

def test_headers_protect_the_html_and_leave_scripts_and_data_compressible():
    h = (ROOT / "web" / "public" / "_headers").read_text()
    blocks = [b for b in re.split(r"(?m)^(?=/)", h) if b.startswith("/")]
    star, page = next(b for b in blocks if b.startswith("/*")), next(b for b in blocks if b.startswith("/\n"))
    assert "must-revalidate" in star and "no-transform" not in star and "no-transform" in page

def test_the_service_worker_caches_only_an_allowlist():
    sw = (ROOT / "web" / "public" / "sw.js").read_text()
    assert "CACHEABLE" in sw and "!CACHEABLE(u.pathname)" in sw and "/v1" not in sw.split("CACHEABLE = ")[1].split(";")[0]


def test_every_page_has_a_title_a_description_a_canonical_url_and_parseable_structured_data():
    pages = sorted((ROOT / "p").glob("*/index.html"))
    assert pages
    for f in pages[::97]:
        h = f.read_text(); slug = f.parent.name
        assert re.search(r"<title>[^<]+ · AirStack</title>", h) and '<meta name="description" content="' in h
        assert f'<link rel="canonical" href="https://airstack.bot/p/{slug}/">' in h
        lds = [json.loads(ld) for ld in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h)]
        crumb = next(ld for ld in lds if ld["@type"] == "BreadcrumbList")
        assert all("item" in row for row in crumb["itemListElement"][:-1])

def test_the_sitemap_names_each_crawlable_page_once():
    root = ET.parse(paths.SITEMAP).getroot(); ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [n.text for n in root.findall("s:url/s:loc", ns)]
    pages = {"https://airstack.bot/", "https://airstack.bot/open-data/"} | {f"https://airstack.bot/{p.parent.relative_to(ROOT).as_posix()}/" for d in ("c", "calendar", "compare", "insights", "method", "o", "p", "t") for p in (ROOT / d).rglob("index.html")}
    assert len(urls) == len(set(urls)) and set(urls) == pages
    assert not root.findall("s:url/s:lastmod", ns)

def test_every_crawlable_page_has_an_inbound_html_link():
    root = ET.parse(paths.SITEMAP).getroot(); ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    expected = {"/" + n.text.split("airstack.bot/", 1)[1] for n in root.findall("s:url/s:loc", ns)} - {"/"}
    pages = [ROOT / "web" / "index.html", paths.OPEN_DATA / "index.html"] + [p for d in paths.PAGE_DIRS.values() for p in d.rglob("index.html")]
    linked = set()
    for page in pages:
        text = page.read_text(); linked.update(re.findall(r'href="(/[^"#?]*/)', text))
        route = "/" if page == ROOT / "web" / "index.html" else "/open-data/" if page == paths.OPEN_DATA / "index.html" else f'/{page.parent.relative_to(ROOT).as_posix()}/'
        assert text.count("<h1") == 1 and f'<link rel="canonical" href="https://airstack.bot{route}">' in text, route
    assert not expected - linked, sorted(expected - linked)[:20]

def test_an_offer_or_a_price_on_a_page_is_always_a_sourced_list_price():
    prices = json.loads(paths.PRICING.read_text())
    for pid, q in list(prices.items())[:60]:
        f = ROOT / "p" / re.sub(r"[^a-z0-9]+", "-", pid.lower()).strip("-")[:60] / "index.html"
        if not f.exists(): continue
        h = f.read_text()
        ld = json.loads(re.findall(r'<script type="application/ld\+json">(.*?)</script>', h)[0])
        for o in ld.get("offers", []):
            assert o["url"] == q["url"] and any(o["name"] == p["plan"] for p in q["plans"])
        shown = set(re.findall(r'title="[^"]*">([^<]*[$€£¥][^<]*)</a>', h))
        assert shown <= {p["price"] for p in q["plans"]}

def test_every_alternative_link_points_at_a_page_that_exists():
    for f in sorted((ROOT / "p").glob("*/index.html"))[::211]:
        for slug in re.findall(r'href="/p/([^/"]+)/"', f.read_text()):
            assert (ROOT / "p" / slug / "index.html").exists(), (f.parent.name, slug)

def test_every_organization_page_is_citable_and_links_only_what_exists():
    pages = sorted((ROOT / "o").glob("*/index.html"))
    assert pages
    for f in pages[::53]:
        h = f.read_text(); slug = f.parent.name
        assert f'<link rel="canonical" href="https://airstack.bot/o/{slug}/">' in h
        ld = json.loads(re.findall(r'<script type="application/ld\+json">(.*?)</script>', h)[0])
        assert ld["@type"] == "Organization" and any(u.startswith("https://www.wikidata.org/wiki/Q") for u in ld["sameAs"])
        for p in re.findall(r'href="/p/([^/"]+)/"', h):
            assert (ROOT / "p" / p / "index.html").exists(), (slug, p)
        assert "linkedin.com/in/" not in h and 'href="mailto:' not in h, slug

def test_a_product_page_links_its_maker_to_a_page_that_exists():
    for f in sorted((ROOT / "p").glob("*/index.html"))[::97]:
        for o in re.findall(r'href="/o/([^/"]+)/"', f.read_text()):
            assert (ROOT / "o" / o / "index.html").exists(), (f.parent.name, o)

def test_every_category_page_lists_its_products_and_shows_only_sourced_prices():
    prices = json.loads(paths.PRICING.read_text())
    pages = sorted((ROOT / "c").glob("*/index.html"))
    assert pages
    quoted = {pl["price"] for q in prices.values() for pl in q["plans"]}
    for f in pages:
        h = f.read_text()
        ld = json.loads(re.findall(r'<script type="application/ld\+json">(.*?)</script>', h)[0])
        links = re.findall(r'<td><a href="/p/([^/"]+)/">', h)
        assert ld["@type"] == "CollectionPage" and ld["mainEntity"]["numberOfItems"] == len(links) > 0, f.parent.name
        assert all((ROOT / "p" / ln / "index.html").exists() for ln in links), f.parent.name
        assert set(re.findall(r'rel="nofollow noopener" title="[^"]*">([^<]*)</a> <small>', h)) <= quoted, f.parent.name

def test_a_comparison_page_exists_only_where_both_products_state_enough_of_the_same_facts():
    from pages.comparison import SHARED
    pages = sorted((ROOT / "compare").glob("*-vs-*/index.html"))
    for f in pages[::41]:
        h = f.read_text(); a, b = re.findall(r'<th><a href="/p/([^/"]+)/">', h)
        assert f.parent.name == f"{a}-vs-{b}" and (ROOT / "p" / a / "index.html").exists() and (ROOT / "p" / b / "index.html").exists()
        both = [r for r in re.findall(r"<tr><th>[^<]*</th><td>(.*?)</td><td>(.*?)</td></tr>", h, re.S) if "Not observed" not in r[0] + r[1]]
        assert len(both) >= SHARED, f.parent.name
        assert f'href="/compare/{f.parent.name}/"' in (ROOT / "p" / a / "index.html").read_text()
        differences = h.split(" differ?</h2>", 1)[-1].split("<p><small>Prices are", 1)[0]
        assert not re.search(r"\b(winner|better|best|recommend(ed)?)\b", re.sub(r"<[^>]+>", " ", differences), re.I)

def test_the_generated_pages_stay_under_the_hosts_file_limit():
    """The host serves at most 20,000 files per version, and comparison pages grow with the square of a category."""
    files = [p for d in ("c", "compare", "p", "o", "t") for p in (ROOT / d).rglob("*") if p.is_file()]
    n, size = len(files), sum(p.stat().st_size for p in files)
    assert n < 19000 and size < 100_000_000, f"{n} generated pages use {size:,} bytes"

def org_qid(slug):
    """The Wikidata item a maker page is about."""
    return re.search(r"wikidata\.org/wiki/(Q\d+)", (ROOT / "o" / slug / "index.html").read_text()).group(1)

@functools.cache
def wikidata_product_pages():
    return [f for f in sorted((ROOT / "p").glob("*/index.html")) if "wikidata.org/wiki/Q" in f.read_text()]

def test_every_maker_page_lists_a_product_and_the_leaderboard_ranks_only_what_wikidata_dates():
    import html as H
    D = json.loads(paths.DIRECTORY.read_text()); bad = set(D.get("implausible", {}))
    for f in sorted((ROOT / "o").glob("*/index.html"))[::29]:
        assert "listed on AirStack" in re.search(r'name="description" content="([^"]*)"', f.read_text()).group(1), f.parent.name
    hub = (ROOT / "o" / "index.html").read_text()
    first = hub.split("<h2>Most products listed</h2>")[0]
    rows = re.findall(r'<tr><td>(\d+)</td><td><a href="/o/([^/"]+)/">', first)
    assert rows and [int(r[0]) for r in rows] == list(range(1, len(rows) + 1))
    qids = [org_qid(r[1]) for r in rows]
    heads = [D["orgs"][q][6] for q in qids]
    assert all(D["orgs"][q][5] == "business" and D["orgs"][q][7] and q not in bad for q in qids) and heads == sorted(heads, reverse=True)
    for slug in {s for _, s in rows}: assert (ROOT / "o" / slug / "index.html").exists()
    for c in sorted((ROOT / "o" / "in").glob("*/index.html"))[::7]:
        h = c.read_text(); name = H.unescape(re.search(r"<h1>Software makers in (.*?)</h1>", h).group(1))
        for s_ in re.findall(r'<td><a href="/o/([^/"]+)/">', h):
            assert D["orgs"][org_qid(s_)][2] == name, (c.parent.name, s_)

def test_pages_never_show_another_sites_prices_invented_alternatives_or_claims_the_table_does_not_hold():
    import pages.data as bp
    orgs = json.loads(paths.DIRECTORY.read_text())["orgs"]
    for f in wikidata_product_pages()[::23]:
        h = f.read_text()
        assert "alternatives</h2>" not in h.replace("Open-source alternatives", ""), f.parent.name
        for u in re.findall(r'<td><a href="([^"]+)" rel="nofollow noopener" title=', h):
            home = re.search(r'"sameAs": \["([^"]+)"', h)
            assert home and bp.site(u) == bp.site(home.group(1)) and bp.site(u) not in bp.HOSTS - {bp.site(home.group(1))}, (f.parent.name, u)
    for f in sorted((ROOT / "c").glob("*/index.html")):
        for plan in re.findall(r'</a> <small>([^<·]+?)(?: · per user)?(?: / (?:month|year))?</small>', f.read_text()):
            assert not bp.ADDON.search(plan), (f.parent.name, plan)
    for f in sorted((ROOT / "compare").glob("*/index.html"))[::31]:
        h = f.read_text(); assert "publishes a paid list price" not in h and "among its platforms" not in h, f.parent.name
    for f in sorted((ROOT / "o" / "in").glob("*/index.html")):
        ranked = f.read_text().split("<main>")[1].split("Every other maker")[0]
        assert all(orgs[org_qid(s)][5] == "business"
                   for s in re.findall(r'<td><a href="/o/([^/"]+)/">', ranked)), f.parent.name

def test_every_internal_link_on_the_maker_and_category_hubs_leads_to_a_page():
    for hub in [ROOT / "o" / "index.html", *sorted((ROOT / "o" / "in").glob("*/index.html"))[::5], *sorted((ROOT / "c").glob("*/index.html"))[::4], ROOT / "t" / "index.html", *sorted((ROOT / "t").glob("*/index.html"))[::9]]:
        for path in set(re.findall(r'href="(/(?:o|c|p|compare|t)/[^"#]*)"', hub.read_text())):
            assert (ROOT / path.strip("/") / "index.html").exists(), (hub.relative_to(ROOT).as_posix(), path)

def test_the_makers_view_data_ranks_exactly_what_the_hub_ranks():
    M = json.loads((ROOT / "o" / "makers.json").read_text())
    hub = re.findall(r'<tr><td>(\d+)</td><td><a href="/o/([^/"]+)/">', (ROOT / "o" / "index.html").read_text().split("<h2>Most products listed</h2>")[0])
    ranked = [r[0] for r in M["rows"] if r[7]]
    assert ranked[:len(hub)] == [slug for _, slug in hub] and len(ranked) == M["ranked"]
    assert all(r[4] is None or r[5] for r in M["rows"]) and all((ROOT / "o" / r[0] / "index.html").exists() for r in M["rows"][::17])
    assert all(c in M["countries"] for c in {r[2] for r in M["rows"] if r[2]})

def test_the_software_taxonomy_pages_place_each_product_once_and_say_how_much_is_not_placed():
    idx = json.loads(paths.TAXONOMY_INDEX.read_text()); N = {n["id"]: n for n in json.loads(paths.TAXONOMY.read_text())["nodes"]}
    hub = (ROOT / "t" / "index.html").read_text()
    assert f'{idx["summary"]["placed"]:,}' in hub and f'{idx["summary"]["products"]:,}' in hub
    pages = sorted((ROOT / "t").glob("*/index.html")); assert pages and {pp.parent.name for pp in pages} <= set(N)
    for f in pages[::7]:
        h = f.read_text(); ld = json.loads(re.findall(r'<script type="application/ld\+json">(.*?)</script>', h)[0])
        assert ld["@type"] == "CollectionPage" and f'<link rel="canonical" href="https://airstack.bot/t/{f.parent.name}/">' in h
        for path in set(re.findall(r'href="(/(?:t|p)/[^"#]*)"', h)): assert (ROOT / path.strip("/") / "index.html").exists(), (f.parent.name, path)
        assert not re.search(r"\b(best|winner|recommended|ranking)\b", re.sub(r"<[^>]+>", " ", re.sub(r"<table>.*?</table>", "", h.split("<main>")[1], flags=re.S)), re.I), f.parent.name      # a list, not a ranking (the table holds vendors' own words)
    product_pages = sorted((ROOT / "p").glob("*/index.html"))
    assert any(re.search(r'href="/(?:t|c)/[^/]+/"', page.read_text()) for page in product_pages)

def test_the_type_map_data_agrees_with_the_taxonomy_pages():
    M = json.loads((ROOT / "t" / "map.json").read_text()); idx = json.loads((paths.TAXONOMY_INDEX).read_text())
    assert M["placed"] == idx["summary"]["placed"] and M["total"] == idx["summary"]["products"]
    for nid in sorted(nid for nid, node in M["nodes"].items() if node[1] is None)[:3]:
        name, parent, listed, read, top = M["nodes"][nid]
        assert parent is None and f"{listed:,} listed products" in (ROOT / "t" / nid / "index.html").read_text()
        assert [r[2] for r in top] == sorted((r[2] for r in top), reverse=True) and len(top) <= 36
        assert all(r[0] in idx["products"] for r in top)


def test_the_site_builds_the_same_bytes_under_any_hash_seed(tmp_path):
    import os
    import subprocess
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "TMPDIR": str(tmp_path)}
        subprocess.run([str(ROOT / "tools" / "assemble.sh"), str(tmp_path / seed)], cwd=ROOT, env=env, check=True, capture_output=True)
    differ = [p.relative_to(tmp_path / "1") for p in (tmp_path / "1").rglob("*") if p.is_file() and p.read_bytes() != (tmp_path / "2" / p.relative_to(tmp_path / "1")).read_bytes()]
    assert not differ, differ[:5]
