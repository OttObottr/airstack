# spec: AS-142 AS-248 AS-252 AS-257 AS-285 AS-317 AS-318 AS-319
from conftest import ROOT
import functools, gzip, json, pytest, re
from airstack import paths


# --- pages: Static product pages: crawlable, citable, and never showing a price that isn't a sourced list price. ---

def test_every_page_has_a_title_a_description_a_canonical_url_and_parseable_structured_data():
    pages = sorted((ROOT / "p").glob("*/index.html"))
    assert len(pages) > 1000
    for f in pages[::97]:
        h = f.read_text(); slug = f.parent.name
        assert re.search(r"<title>[^<]+ · AirStack</title>", h) and '<meta name="description" content="' in h
        assert f'<link rel="canonical" href="https://airstack.bot/p/{slug}/">' in h
        for ld in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h):
            json.loads(ld)

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
    """AS-317: a page per maker: Organization structured data with its Wikidata item, a canonical address, and product links that resolve."""
    pages = sorted((ROOT / "o").glob("*/index.html"))
    assert len(pages) > 1000
    for f in pages[::53]:
        h = f.read_text(); slug = f.parent.name
        assert f'<link rel="canonical" href="https://airstack.bot/o/{slug}/">' in h
        ld = json.loads(re.findall(r'<script type="application/ld\+json">(.*?)</script>', h)[0])
        assert ld["@type"] == "Organization" and any(u.startswith("https://www.wikidata.org/wiki/Q") for u in ld["sameAs"])
        for p in re.findall(r'href="/p/([^/"]+)/"', h):
            assert (ROOT / "p" / p / "index.html").exists(), (slug, p)
        visible = re.sub(r"<script[\s\S]*?</script>", "", h, flags=re.I).split("People")[-1][:400]
        assert "linkedin.com/in/" not in h and "@" not in visible, slug   # people by name and role only

def test_a_product_page_links_its_maker_to_a_page_that_exists():
    for f in sorted((ROOT / "p").glob("*/index.html"))[::97]:
        for o in re.findall(r'href="/o/([^/"]+)/"', f.read_text()):
            assert (ROOT / "o" / o / "index.html").exists(), (f.parent.name, o)

def test_every_category_page_lists_its_products_and_shows_only_sourced_prices():
    """AS-318: a page per category; every product row links a page that exists; every price shown is a list price quoted on its pricing page."""
    prices = json.loads(paths.PRICING.read_text())
    pages = sorted((ROOT / "c").glob("*/index.html"))
    assert len(pages) >= 30
    quoted = {pl["price"] for q in prices.values() for pl in q["plans"]}
    for f in pages:
        h = f.read_text()
        ld = json.loads(re.findall(r'<script type="application/ld\+json">(.*?)</script>', h)[0])
        links = re.findall(r'<td><a href="/p/([^/"]+)/">', h)
        assert ld["@type"] == "CollectionPage" and ld["mainEntity"]["numberOfItems"] == len(links) > 0, f.parent.name
        assert all((ROOT / "p" / l / "index.html").exists() for l in links), f.parent.name
        assert set(re.findall(r'rel="nofollow noopener" title="[^"]*">([^<]*)</a> <small>', h)) <= quoted, f.parent.name

def test_a_comparison_page_exists_only_where_both_products_state_enough_of_the_same_facts():
    """AS-319: side by side from each product's own pages; a pair earns a page only with SHARED facts stated on both sides; nothing is ranked."""
    import build_pages as bp
    pages = sorted((ROOT / "compare").glob("*-vs-*/index.html"))
    assert len(pages) > 1000
    for f in pages[::41]:
        h = f.read_text(); a, b = re.findall(r'<th><a href="/p/([^/"]+)/">', h)
        assert f.parent.name == f"{a}-vs-{b}" and (ROOT / "p" / a / "index.html").exists() and (ROOT / "p" / b / "index.html").exists()
        both = [r for r in re.findall(r"<tr><th>[^<]*</th><td>(.*?)</td><td>(.*?)</td></tr>", h, re.S) if "Not observed" not in r[0] + r[1]]
        assert len(both) >= bp.SHARED, f.parent.name
        assert f'href="/compare/{f.parent.name}/"' in (ROOT / "p" / a / "index.html").read_text()
        assert not re.search(r"\b(winner|better|best|recommend(ed)?)\b", re.sub(r"<[^>]+>", " ", h).split("Where they differ")[-1].split("Prices are")[0], re.I)

def test_the_generated_pages_stay_under_the_hosts_file_limit():
    """Cloudflare serves at most 20,000 files per Worker version on the free plan. Comparison pages grow with research (pairs grow as the
    square of a category's researched products), so the build fails here, with room to spare, before a deploy would fail at the host.
    Over the line: raise compare_pages' SHARED threshold or cap pairs per category; never drop product, maker or category pages."""
    files = [p for d in ("c", "compare", "p", "o", "t") for p in (ROOT / d).rglob("*") if p.is_file()]
    n, size = len(files), sum(p.stat().st_size for p in files)
    assert n < 19000 and size < 100_000_000, f"{n} generated pages use {size:,} bytes"

def org_qid(slug):
    """The Wikidata item a maker page is about, read from the page (addresses are readable names, not ids)."""
    return re.search(r"wikidata\.org/wiki/(Q\d+)", (ROOT / "o" / slug / "index.html").read_text()).group(1)

@functools.cache
def wikidata_product_pages():
    return [f for f in sorted((ROOT / "p").glob("*/index.html")) if "wikidata.org/wiki/Q" in f.read_text()]

def test_every_maker_page_lists_a_product_and_the_leaderboard_ranks_only_what_wikidata_dates():
    """AS-317: a maker page exists only for a maker with a product listed; /o/ ranks businesses by a dated headcount, never an undated
    or implausible one; every country page lists only makers in that country, and every link resolves."""
    import html as H
    D = json.loads(paths.DIRECTORY.read_text()); bad = set(D.get("implausible", {}))
    for f in sorted((ROOT / "o").glob("*/index.html"))[::29]:
        assert "listed on AirStack" in re.search(r'name="description" content="([^"]*)"', f.read_text()).group(1), f.parent.name
    hub = (ROOT / "o" / "index.html").read_text()
    first = hub.split("<h2>Most products listed</h2>")[0]
    rows = re.findall(r'<tr><td>(\d+)</td><td><a href="/o/([^/"]+)/">', first)
    assert len(rows) == 100 and [int(r[0]) for r in rows] == list(range(1, 101))
    qids = [org_qid(r[1]) for r in rows]
    heads = [D["orgs"][q][6] for q in qids]
    assert all(D["orgs"][q][5] == "business" and D["orgs"][q][7] and q not in bad for q in qids) and heads == sorted(heads, reverse=True)
    for slug in {s for _, s in rows}: assert (ROOT / "o" / slug / "index.html").exists()
    for c in sorted((ROOT / "o" / "in").glob("*/index.html"))[::7]:
        h = c.read_text(); name = H.unescape(re.search(r"<h1>Software makers in (.*?)</h1>", h).group(1))
        for s_ in re.findall(r'<td><a href="/o/([^/"]+)/">', h):
            assert D["orgs"][org_qid(s_)][2] == name, (c.parent.name, s_)

def test_pages_never_show_another_sites_prices_invented_alternatives_or_claims_the_table_does_not_hold():
    """The reviewer's findings, kept fixed: a price is shown only when read on the product's own site (not a shared host's pricing page);
    a directory listing gets no alternatives list (its lane is everything Wikidata lists); a starting price is a plan, never an add-on;
    comparison pages make no price or platform claims; country pages rank only businesses."""
    import build_pages as bp
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
        ranked = f.read_text().split("<main>")[1].split("Every other maker")[0]                       # the visible ranked table, not the structured data
        assert "Ministry" not in ranked and "Bundeswehr" not in ranked and "University" not in ranked, f.parent.name

def test_every_internal_link_on_the_maker_and_category_hubs_leads_to_a_page():
    """The makers hub once linked 26 countries that had no page (live 404s): every /o/, /c/, /p/ and /compare/ link on the hubs must exist."""
    for hub in [ROOT / "o" / "index.html", *sorted((ROOT / "o" / "in").glob("*/index.html"))[::5], *sorted((ROOT / "c").glob("*/index.html"))[::4], ROOT / "t" / "index.html", *sorted((ROOT / "t").glob("*/index.html"))[::9]]:
        for path in set(re.findall(r'href="(/(?:o|c|p|compare|t)/[^"#]*)"', hub.read_text())):
            assert (ROOT / path.strip("/") / "index.html").exists(), (hub.relative_to(ROOT).as_posix(), path)

def test_the_makers_view_data_ranks_exactly_what_the_hub_ranks():
    """o/makers.json is written by the same function as the /o/ hub, so the app's Makers view can never disagree with the static pages."""
    M = json.loads((ROOT / "o" / "makers.json").read_text())
    hub = re.findall(r'<tr><td>(\d+)</td><td><a href="/o/([^/"]+)/">', (ROOT / "o" / "index.html").read_text().split("<h2>Most products listed</h2>")[0])
    ranked = [r[0] for r in M["rows"] if r[7]]
    assert ranked[:len(hub)] == [slug for _, slug in hub] and len(ranked) == M["ranked"]
    assert all(r[4] is None or r[5] for r in M["rows"]) and all((ROOT / "o" / r[0] / "index.html").exists() for r in M["rows"][::17])
    assert all(c in M["countries"] for c in {r[2] for r in M["rows"] if r[2]})

def test_the_software_taxonomy_pages_place_each_product_once_and_say_how_much_is_not_placed():
    """AS-285: /t/ and /t/<node>/ are built from data/taxonomy.json and taxonomy-index.json: every node with products has a page, every child link and
    product link resolves, the numbers match the index, and the hub states how many listed products carry no category yet (never a guess)."""
    I = json.loads(paths.TAXONOMY_INDEX.read_text()); N = {n["id"]: n for n in json.loads(paths.TAXONOMY.read_text())["nodes"]}
    hub = (ROOT / "t" / "index.html").read_text()
    m = re.search(r"([\d,]+) of ([\d,]+) listed products are placed in a category. The other ([\d,]+)", hub)
    assert [int(g.replace(",", "")) for g in m.groups()] == [I["summary"]["placed"], I["summary"]["products"], I["summary"]["products"] - I["summary"]["placed"]]
    pages = sorted((ROOT / "t").glob("*/index.html")); assert len(pages) > 200 and {pp.parent.name for pp in pages} <= set(N)
    for f in pages[::7]:
        h = f.read_text(); ld = json.loads(re.findall(r'<script type="application/ld\+json">(.*?)</script>', h)[0])
        assert ld["@type"] == "CollectionPage" and f'<link rel="canonical" href="https://airstack.bot/t/{f.parent.name}/">' in h
        for path in set(re.findall(r'href="(/(?:t|p)/[^"#]*)"', h)): assert (ROOT / path.strip("/") / "index.html").exists(), (f.parent.name, path)
        assert not re.search(r"\b(best|winner|recommended|ranking)\b", re.sub(r"<[^>]+>", " ", re.sub(r"<table>.*?</table>", "", h.split("<main>")[1], flags=re.S)), re.I), f.parent.name      # a list, not a ranking (the table holds vendors' own words)
    assert 'href="/t/design/"' in (ROOT / "p" / "figma" / "index.html").read_text() or 'href="/c/design/"' in (ROOT / "p" / "figma" / "index.html").read_text()

def test_the_type_map_data_agrees_with_the_taxonomy_pages():
    """t/map.json feeds the Markets picker; its counts, order and names must be the ones the /t/ pages state, and every tile's product must be classified."""
    M = json.loads((ROOT / "t" / "map.json").read_text()); I = json.loads((paths.TAXONOMY_INDEX).read_text())
    assert M["placed"] == I["summary"]["placed"] and M["total"] == I["summary"]["products"]
    for nid in ("design", "engineering", "consumer"):
        name, parent, listed, read, top = M["nodes"][nid]
        assert parent is None and f"{listed:,} listed products" in (ROOT / "t" / nid / "index.html").read_text()
        assert [r[2] for r in top] == sorted((r[2] for r in top), reverse=True) and len(top) <= 36
        assert all(r[0] in I["products"] for r in top)


# --- agent_layer: The agent layer (CLAUDE.md, .claude/skills, .claude/agents) is documentation that agents act on, so it is tested like code: ---

SKILLS = sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md"))

AGENTS = sorted((ROOT / ".claude" / "agents").glob("*.md"))

FILES = SKILLS + AGENTS + [ROOT / "CLAUDE.md"]

def frontmatter(p):
    m = re.match(r"---\n(.*?)\n---\n", p.read_text(), re.S)
    assert m, f"{p} has no frontmatter"
    return dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line)

def test_every_skill_and_agent_has_a_matching_name_and_a_description():
    assert len(SKILLS) >= 6 and len(AGENTS) >= 3
    for p in SKILLS:
        fm = frontmatter(p); assert fm["name"] == p.parent.name and len(fm["description"]) > 40, p
    for p in AGENTS:
        fm = frontmatter(p); assert fm["name"] == p.stem and fm["tools"] and fm["description"], p

def test_the_index_in_claude_md_lists_every_skill_and_agent():
    index = (ROOT / "CLAUDE.md").read_text()
    assert all(f"`{p.parent.name}`" in index for p in SKILLS) and all(f"`{p.stem}`" in index for p in AGENTS)

def test_every_file_and_tool_they_name_exists():
    for p in FILES:
        text = p.read_text()
        for path in set(re.findall(r"(?<![\w/.-])((?:backend|tools|docs|SPECS|JOURNEY)/[\w./-]*\w\.(?:py|md|sh|json))", text)):
            if path.startswith("data/"):
                continue
            assert (ROOT / path).exists(), f"{p.name} names {path}, which does not exist"
        for path in set(re.findall(r"(?<![\w/.-])(\.githooks/\w+|\.gitleaks\.toml)", text)):
            assert (ROOT / path).exists(), f"{p.name} names {path}"

def test_the_safety_rules_are_present_and_nothing_host_specific_leaks_in():
    claude = (ROOT / "CLAUDE.md").read_text()
    assert "Never read, print, copy or type `.env` values" in claude and "explicit yes" in claude and "Less code is better" in claude
    for p in FILES:
        text = p.read_text()
        assert not re.search(r"/Users/|/home/\w+/", text, re.I), p
        assert "LLM_" not in text and "sk-" not in text


# --- content_policy: AirStack lists legitimate software and services: nothing mainly for piracy, adult content, illegal markets or malware (config/excluded.json). ---

POLICY = paths.config("excluded")

TEXT, TYPE = re.compile(POLICY["text"], re.I), re.compile(POLICY["type_labels"], re.I)

def listed():
    D = json.loads(paths.DIRECTORY.read_text())
    return D, [(p, D["types"][p[4]][1]) for p in D["products"]]

def test_no_listing_matches_the_policy():
    D, rows = listed()
    bad = [(p[1], t) for p, t in rows if p[0] in POLICY["ids"] or TEXT.search(f"{p[1]} {p[2] or ''}") or TYPE.match(t)]
    assert not bad, bad[:5]
    assert not [o[0] for o in D["orgs"].values() if TEXT.search(o[0])]

def test_legitimate_neighbours_of_excluded_categories_stay_listed():
    names = {p[1] for p, _ in listed()[1]}
    assert {"qBittorrent", "Transmission", "Aircrack-ng"} <= names        # clients and security tools are software; trackers and index sites are not

def test_a_label_carrying_vandalism_is_listed_under_its_real_name():
    names = {p[0]: p[1] for p, _ in listed()[1]}
    assert all(names.get(i) == n for i, n in POLICY["renames"].items() if i in names)

def test_nothing_excluded_reaches_published_research():
    ids = set(json.loads(paths.EXCLUDED.read_text())) if paths.EXCLUDED.exists() else pytest.skip("needs data/excluded.json (written by build_directory.py)")
    assert ids, "the policy removed nothing: check config/excluded.json"
    assert not ids & set(json.loads(paths.PROFILES.read_text())) and not ids & set(json.loads(paths.CHAIN_DATA.read_text())["entities"])
    assert not ids & set(json.loads(paths.COMMUNITY.read_text())["entities"])
    for f in paths.OPEN_DATA.glob("airstack-*.jsonl.gz"):
        assert not any(json.loads(l).get("id") in ids for l in gzip.open(f, "rt")), f.name

def test_no_published_file_names_a_blocked_site():
    """Whatever the source, a file the site serves never names an excluded brand (a junk alias, a stored label, a sitemap entry)."""
    brands = re.compile(r"xnxx|xvideos|pornhub|xhamster|thepiratebay|pirate-bay|1337x\.to|rutracker|kickasstorrents", re.I)
    for f in paths.SITE.rglob("*"):
        if f.is_file() and f.suffix in (".json", ".js", ".atom", ".xml", ".svg", ".md"):
            assert not brands.search(f.read_text(errors="ignore")), f.name
