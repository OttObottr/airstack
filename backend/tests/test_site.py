# spec: AS-013 AS-121 AS-131 AS-202 AS-252 AS-256 AS-280 AS-297 AS-343 AS-351 AS-D03
from conftest import ROOT
import html, importlib.util, json, pathlib, pytest, re, shutil, struct, subprocess
from airstack import paths


# --- site: The static site: structured data tells the truth, crawl files exist, and deploy ships everything the page loads. ---

WEB = [ROOT / "web" / "index.html", *sorted((ROOT / "web" / "src").rglob("*.js")), *sorted((ROOT / "web" / "src").rglob("*.css"))]

INDEX = "\n".join(p.read_text() for p in WEB)          # the page: its HTML shell and every module and stylesheet it is built from

def test_structured_data_says_only_what_the_page_says():
    """The FAQ was cut from the page, so its FAQPage markup went too: structured data may not describe content a visitor can't see."""
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

def test_llms_txt_publishes_the_canonical_local_mcp_contract():
    text = (ROOT / "web" / "public" / "llms.txt").read_text()
    published = text.split("Local MCP tools: ", 1)[1].split(". Start with", 1)[0].split(", ")
    from airstack.mcp_server import DESCRIPTIONS
    canonical = sorted(DESCRIPTIONS)
    assert published == canonical

@pytest.mark.skipif(not shutil.which("node"), reason="node reads site-data.js")
def test_llms_txt_only_cites_references_the_checker_verifies():
     
    import verify_references as vr
    verified = {"https://" + e["url"] for _, e in vr.load_rows() if e.get("real") and e.get("url")}
    cited = {u for u in re.findall(r"https://[^\s)]+", (ROOT / "web" / "public" / "llms.txt").read_text()) if not u.startswith("https://airstack.bot/")}   # our own endpoints are not external references
    assert cited and cited <= verified, cited - verified

def test_deploy_ships_every_local_file_the_page_loads():
    assemble = (ROOT / "tools" / "assemble.sh").read_text()
    shipped = {f.split("/")[-1] for line in re.findall(r'^cp (?:-R )?(.+?) "\$out"/$', assemble, re.M) for f in line.split()}
    shipped |= {f.name for f in (ROOT / "web" / "public").iterdir()} | {f.name for f in paths.SITE.iterdir()}                                          # data/site is copied whole: it is what is published
    refs = set(re.findall(r'(?:href|src)="(?![a-z][\w+.-]*:|#|\$\{)([^"]+)"', INDEX)) | {"sw.js", "manifest.webmanifest"} | set(re.findall(r"fetch\('([\w./-]+)'", INDEX))
    refs = {r.lstrip("/") for r in refs}   # fetch('chain-data.json')   # ${...}: links built from data
    assert {"src/main.js", "src/styles/index.css"} <= refs and '(web / "src").rglob("*.js")' in assemble   # the modules ship as files from web/src; the stylesheets are inlined
    refs = {r for r in refs if not (r.startswith("src/") and (ROOT / "web" / r).is_file())}
    refs |= {i["src"] for i in json.loads((ROOT / "web" / "public" / "manifest.webmanifest").read_text())["icons"]}
    refs |= set(re.findall(r"'([\w./-]+\.(?:html|js|webmanifest|woff2|png))'", (ROOT / "web" / "public" / "sw.js").read_text())) - {"./"}
    missing = [r for r in refs if r not in shipped and r.split("/")[0] not in shipped]
    assert not missing, missing

@pytest.mark.skipif(not shutil.which("node"), reason="node reads site-data.js")
def test_card_faces_hold_plain_english_only():
    """Card copy contains product language rather than record internals."""
    js = "global.window={};require(%r);console.log(JSON.stringify(window.AIRSTACK_DATA))" % str(paths.SITE_DATA)
    data = json.loads(subprocess.check_output(["node", "-e", js], text=True))
    face = []
    for a in data["pool"]:
        face += [a["line"], a["reason"], a["changesIf"], *[n["label"] for n in a["needs"]], *[s["label"] for s in a["sources"]]]
    for st in data["life"]["steps"]:
        face += [st["caption"]["text"], *[r["note"] for r in st["rows"]]]
    face += data["life"]["labels"] + [r["what"] + " " + r["why"] for h in data["history"] for r in h["rows"]]
    face += [s["fact"] + " " + s["source"] for s in data["sources"]]
    assert not [t for t in face if re.search(r"\bseat\b|\bverdict\b|\blapsed\b", t, re.I)], "plain words: you, answer, needs a second look"
    bad = re.compile(r"\b[a-z]+\.[a-z_]{3,}\b|sha256|fake-|fixture|\btokens?\b|\b[0-9a-f]{8}\b", re.I)
    leaks = [(t, m.group(0)) for t in face for m in [bad.search(t)] if m]
    assert not leaks, leaks

def test_share_card_exists_and_is_the_size_its_tags_promise():
    ref = re.search(r'og:image" content="https://airstack\.bot/([^"]+)"', INDEX).group(1)
    png = (ROOT / "web" / "public" / ref).read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", png[16:24]) == (1200, 630) and len(png) < 150_000
    assert 'name="twitter:card" content="summary_large_image"' in INDEX and 'og:image:width" content="1200"' in INDEX

def test_no_live_answer_shows_the_replay_clock_as_its_check_date():
    """Live answers use current check dates rather than the replay timeline."""
    from datetime import date, timedelta
    site, market = paths.read_js(paths.SITE_DATA), paths.read_js(paths.MARKET_DATA)
    floor = (date.fromisoformat(site["meta"]["generated_at"][:10]) - timedelta(days=30)).isoformat()
    seen = [s["date"] for a in site["pool"] for s in a.get("sources", [])]
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "checked" and isinstance(v, str) and v[:2] == "20": seen.append(v[:10])
                walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(market["platforms"]); walk(market["platformLanguages"])
    assert len(seen) > 20, "the check must see the answers' sources"
    assert not [d for d in seen if d < floor], sorted({d for d in seen if d < floor})

def test_security_headers_are_on_every_response():
    """Security headers match the static application's browser requirements."""
    star = re.search(r"(?m)^/\*\n((?:[ \t]+.+\n?)+)", (ROOT / "web" / "public" / "_headers").read_text()).group(1)
    hdr = {k.strip().lower(): v.strip() for k, v in (l.split(":", 1) for l in star.splitlines() if l.strip())}
    assert hdr["strict-transport-security"].startswith("max-age=") and "includesubdomains" not in hdr["strict-transport-security"].lower()
    assert hdr["x-frame-options"] == "DENY" and hdr["x-content-type-options"] == "nosniff"
    csp = {d.split()[0]: d.split()[1:] for d in hdr["content-security-policy"].split("; ")}
    assert csp["default-src"] == ["'self'"] and csp["object-src"] == ["'none'"] and csp["base-uri"] == ["'none'"] and csp["frame-ancestors"] == ["'none'"]
    assert all("http" not in v and "*" not in v for vals in csp.values() for v in vals), "no outside origins and no wildcards"
    assert '"workers_dev": false' in (ROOT / "wrangler.jsonc").read_text(), "a second hostname would bypass the zone's firewall rules"

def test_every_scraped_url_goes_through_the_scheme_check():
    """Links built from external data use HTTP or HTTPS."""
    assert re.search(r"const url\s*=\s*u\s*=>", INDEX) and 'href="${esc(' not in INDEX

def test_headers_protect_the_html_and_leave_scripts_and_data_compressible():
    """AS-202: every response is revalidated. `no-transform` is on the HTML only: it keeps Cloudflare from injecting an analytics beacon (which cost the mobile score; removing it was tried on production and
    failed the live beacon test and Lighthouse), but it also stops compression, so scripts and data must not carry it."""
    h = (ROOT / "web" / "public" / "_headers").read_text()
    blocks = [b for b in re.split(r"(?m)^(?=/)", h) if b.startswith("/")]
    star, page = next(b for b in blocks if b.startswith("/*")), next(b for b in blocks if b.startswith("/\n"))
    assert "must-revalidate" in star and "no-transform" not in star and "no-transform" in page
    assert "_headers" in (ROOT / "tools" / "assemble.sh").read_text()

# ---- regressions from the 2026-11-03 audit of commit f74b394 ----
def test_the_service_worker_caches_only_an_allowlist():
    sw = (ROOT / "web" / "public" / "sw.js").read_text()
    assert "CACHEABLE" in sw and "!CACHEABLE(u.pathname)" in sw and "/v1" not in sw.split("CACHEABLE = ")[1].split(";")[0]


# --- numbers: One number, one source: data/numbers.json holds every headline count, computed by tools/update_counts.py from the generated files ---

spec = importlib.util.spec_from_file_location("update_counts", ROOT / "tools" / "update_counts.py")

uc = importlib.util.module_from_spec(spec); spec.loader.exec_module(uc)

N = json.loads((paths.NUMBERS).read_text())

GROUPED = re.compile(r"(?<![\d.,$])\d{1,3}(?:,\d{3})+(?![\d.]|,\d)")      # 1,234 or 12,345,678: how every count of a thousand or more is written

said = lambda f, t: " ".join(re.findall(r">([^<]*)</(?:text|tspan|title|desc)>", t)) if f.endswith(".svg") else t   # an image's words, not its coordinates

@pytest.mark.private_data
def test_numbers_json_is_what_the_data_gives_today():
    assert uc.counts() == N, "config/numbers.json is stale: run tools/update_counts.py"

def test_every_counted_sentence_in_the_readme_and_llms_txt_states_the_number_in_numbers_json():
    for f, rules in uc.RULES.items():
        text = uc.DOCS[f].read_text()
        assert uc.fill(text, rules, N) == text, f"{f} states a count that differs from data/numbers.json: run tools/update_counts.py"

def test_the_stats_card_states_the_same_numbers():
    svg = paths.STATS_SVG.read_text()
    for key, label in (("products", "software products"), ("organizations", "organizations"),
                       ("researched_products", "read from their own pages"), ("list_prices", "list prices, quoted")):
        assert f'>{N[key]:,}</text><text class="lab" y="30">{label}</text>' in svg, f"stats.svg: {label} is not {N[key]:,}"

def test_no_surface_states_a_count_of_a_thousand_or_more_that_numbers_json_does_not_hold():
    known = {f"{v:,}" for v in N.values()}
    for f, path in (("README.md", ROOT / "README.md"), ("llms.txt", ROOT / "web" / "public" / "llms.txt"), ("stats.svg", paths.STATS_SVG)):
        stray = set(GROUPED.findall(said(f, path.read_text()))) - known
        assert not stray, f"{f} states {sorted(stray)}, which is in no rule: add it to tools/update_counts.py or remove it"

def test_a_changed_count_or_a_reworded_sentence_is_caught():
    text, rules = (ROOT / "README.md").read_text(), uc.RULES["README.md"]
    right = f"{N['researched_products']:,} products researched"
    assert right in text
    wrong = text.replace(right, f"{N['researched_products'] + 1:,} products researched")
    assert uc.fill(wrong, rules, N) == text                                          # the wrong number is found and put right
    with pytest.raises(SystemExit):
        uc.fill(text.replace(right, f"{N['researched_products']:,} products studied"), rules, N)   # a sentence a rule no longer finds stops the run
    svg = paths.STATS_SVG.read_text().replace(f">{N['list_prices']:,}<", f">{N['list_prices'] + 1:,}<")
    assert set(GROUPED.findall(said("stats.svg", svg))) - {f"{v:,}" for v in N.values()} == {f"{N['list_prices'] + 1:,}"}   # and a hand-typed count is a stray

def test_the_daily_run_updates_counts_but_leaves_release_to_a_person():
    sh = (ROOT / "tools" / "daily.sh").read_text()
    assert "tools/update_counts.py" in sh and "review and release them manually" in sh
    assert "git add" not in sh and "git commit" not in sh and "git push" not in sh and "tools/deploy.sh" not in sh
    assert "Generated datasets remain outside git" in (ROOT / ".github" / "CONTRIBUTING.md").read_text()

def test_the_docs_say_what_the_record_says_announced_not_shipped_and_what_is_public():
    llms, readme = (ROOT / "web" / "public" / "llms.txt").read_text(), (ROOT / "README.md").read_text()
    assert not re.search(r"\bshipped\b", llms + readme, re.I)                         # the record: announced on 22 Apr, announced as available on 13 Aug
    assert (ROOT / "LICENSE").read_text().startswith("MIT License") and "MIT" in readme
    assert "docs/OWNER.md" in readme and not (ROOT / "docs" / "OPEN_SOURCE.md").exists()
