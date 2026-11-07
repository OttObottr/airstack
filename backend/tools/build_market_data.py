# spec: AS-013 AS-102 AS-134 AS-137 AS-233 AS-237 AS-326 AS-328
"""Writes ../market-data.js from data/airstack-market.db (facts Muse extracted and code verified) and data/airstack-demo.db (Meet).
Loaded with `defer`: the market renders after first paint, so the landing stays fast.

Comparable by construction: one vocabulary per column (devices, meeting apps, compliance), names folded case-insensitively, and
"Not observed" (null) where no verified fact exists. Every cell lists the pages its facts came from and the date they were checked.
Platform answers are deterministic rules over verified quotes; nothing here calls a model.
Usage: ../.venv/bin/python tools/build_market_data.py"""
import json, re, sqlite3
from collections import defaultdict
from airstack.corpus import norm
from airstack.config import FRESH_DAYS
from airstack.store import add_days
from airstack import paths
from airstack.policy import blocked_ids
from airstack.publication import missing_quote_urls

ROOT = paths.ROOT
MARKET = paths.MARKET_DB
DEMO = paths.DEMO_DB
CFG = paths.config("market")                                      # config/market.json
INCUMBENTS = CFG["incumbents"]
MOVERS = paths.MOVERS
from build_movers import LANES                      # one declared lane list (id -> display name) for the data and the page

def movers():
    """Registry and attention signals (data/movers.json, built by tools/build_movers.py from saved API responses)."""
    if not MOVERS.exists():
        return None
    m = json.loads(MOVERS.read_text())
    rows = []
    for t in m["tools"]:
        s = t["signals"]
        py, npm = s.get("pypi_7d") or {}, s.get("npm_7d") or {}
        dl = py if py.get("value") is not None else npm
        reg = "PyPI" if dl is py else "npm"
        pkg = dl.get("package") or ""
        human = (f"https://pypistats.org/packages/{pkg}" if reg == "PyPI" else f"https://www.npmjs.com/package/{pkg}") if pkg else None
        hn, gh = s.get("hn_7d") or {}, s.get("github") or {}
        rows.append({"id": t["id"], "name": t["name"], "lane": t["lane"], "laneName": LANES.get(t["lane"], t["lane"]),
                     "dl": {"value": dl.get("value"), "delta": dl.get("delta_pct"), "vsBase": dl.get("vs_base_pct"), "baseWeeks": dl.get("base_weeks"), "registry": reg if dl.get("value") is not None else None,
                            "url": human, "api": dl.get("url"), "fetched": day(dl.get("fetched_at")),
                            "why": dl.get("delta_reason") or dl.get("reason") or py.get("reason") or npm.get("reason")},
                     "hn": {"value": hn.get("value"), "delta": hn.get("delta"), "query": hn.get("query"), "api": hn.get("url"), "fetched": day(hn.get("fetched_at")),
                            "why": hn.get("reason")},
                     "gh": {"stars": gh.get("stars"), "release": gh.get("last_release"), "released": day(gh.get("last_release_at")),
                            "url": f"https://github.com/{gh['repo']}" if gh.get("repo") else None, "fetched": day(gh.get("fetched_at")), "why": gh.get("reason")}})
    return {"window": m["window"], "generated": day(m["generated_at"]), "notes": m.get("notes", {}), "rows": rows,
            "lanes": [{"id": l["lane"], "name": LANES.get(l["lane"], l["lane"]), "tools": l["tools"], "deltas": l["with_downloads_delta"]} for l in m["lanes"]]}
DEVICES = [tuple(d) for d in CFG["devices"]]
APPS = CFG["apps"]
COMPLIANCE = [tuple(d) for d in CFG["compliance"]]
KIND_RANK = CFG["kind_rank"]
DESCRIPTION_RANK = CFG["description_rank"]

def host(u): return re.sub(r"^www\.", "", u.split("/")[2])
def day(ts): return (ts or "")[:10]

def load():
    c = sqlite3.connect(f"file:{MARKET}?mode=ro", uri=True)
    rows = c.execute("""SELECT f.id, f.entity_id, f.metric, f.value, f.url, f.observed_at, p.quote, p.page_kind, p.call_ref
                        FROM facts f JOIN fact_provenance p ON p.fact_id = f.id ORDER BY f.id""").fetchall()
    facts = defaultdict(lambda: defaultdict(list))
    from airstack.corpus import failing_now, is_bad
    bad = failing_now(c)                                    # admitted under older rules, rejected by today's: never shown (the stored rows stay)
    missing = missing_quote_urls(c)                          # the last successful live check lost at least one supporting quote
    withheld = set(bad) | {(u, q, m) for u, q, m in c.execute("SELECT url, quote, metric FROM verifications WHERE ok=1") if u in missing}
    for fid, e, m, v, u, obs, q, kind, ref in rows:
        if is_bad(bad, u, q, m) or u in missing: continue
        facts[e][m].append({"id": fid, "value": json.loads(v), "url": u, "checked": day(obs), "quote": q, "kind": kind.replace("-plans", ""), "call": ref})
    names = {r[0]: (r[1], r[2], r[3]) for r in c.execute("SELECT id, name, maker, kind FROM entities")}
    fleet = {"pages": c.execute("SELECT count(*) FROM raw_items").fetchone()[0],
             "readable": c.execute("SELECT count(*) FROM raw_items WHERE status=200 AND length(text) >= 500").fetchone()[0],
             "calls": c.execute("SELECT count(*) FROM calls WHERE kind != 'cached' AND call_ref != 'failed' AND model != 'fixture (no model call)'").fetchone()[0],
             "checked": c.execute("SELECT count(*) FROM verifications").fetchone()[0],
             "passed": sum(1 for u, q, m in c.execute("SELECT url, quote, metric FROM verifications WHERE ok=1") if not is_bad(bad, u, q, m) and u not in missing),   # claims today's rules reject are not counted as verified
             "facts": sum(len(v) for per in facts.values() for v in per.values()),                                                              # the facts the page can show, not the rows stored
             "withheld": len(withheld)}
    return facts, names, fleet

def cell(items, value):
    """A table cell: the display value plus where it came from."""
    if value is None or value == [] or items == []:
        return None
    srcs = []
    for f in items:
        if f["url"] not in [s["url"] for s in srcs]:
            srcs.append({"url": f["url"], "host": host(f["url"]), "checked": f["checked"]})
    return {"value": value, "sources": srcs, "checked": max(f["checked"] for f in items)}

def fold(items, canon):
    out, used = [], []
    for f in items:
        hit = False
        for raw in f["value"]:
            c = canon(raw)
            if c and c not in out:
                out.append(c)
            hit = hit or bool(c)
        if hit:
            used.append(f)
    return out, used

def dev(raw):
    r = raw.lower()
    return next((name for pat, name in DEVICES if re.search(pat, r)), None)

def comp(raw):
    r = raw.lower()
    for pat, name in COMPLIANCE:
        if re.search(pat, r):
            return name + (" (add-on)" if "add-on" in r else "")
    return None

def vendor(e, F, names):
    f = F[e]
    by = lambda m, kinds=None: sorted([x for x in f.get(m, []) if not kinds or x["kind"] in kinds], key=lambda x: KIND_RANK.get(x["kind"], 9))
    what = [x for x in by("x.what_it_does") if not CURRENCY.search(x["quote"])]
    langs = by("x.languages_count", {"home", "pricing", "features", "integrations", "chrome"})
    lang = langs[0] if langs else None
    joins, joins_src = fold(by("x.joins_meeting_apps"), lambda r: APPS.get(r.strip().lower()))
    devices, dev_src = fold(by("x.devices"), dev)
    compl, comp_src = fold(by("x.compliance"), comp)
    integ, seen = [], set()
    for x in by("x.integrations"):
        for n in x["value"]:
            k = n.strip().lower()
            if k in seen or k in APPS or k in ("crm", "chat"):
                continue
            seen.add(k); integ.append(n.strip())
    stated = by("x.integrations_count")
    chrome = [x for x in by("x.store_users") if host(x["url"]) == "chromewebstore.google.com"]
    rating = lambda h: [x for x in by("x.store_rating") if host(x["url"]) == h]
    flag = lambda m: cell(by(m), True) if any(x["value"] is True for x in by(m)) else None
    order = ["Web", "Windows", "macOS", "Linux", "Desktop", "iPhone", "iPad", "Android", "Mobile", "Chrome extension"]
    return {"id": e, "name": names[e][0], "maker": names[e][1],
            "what": cell(what[:1], what[0]["quote"]) if what else None,
            "joins": cell(joins_src, sorted(joins, key=lambda a: list(APPS.values()).index(a))),
            "devices": cell(dev_src, sorted(devices, key=order.index)),
            "languages": cell([lang], f"{lang['value']}+" if lang and re.search(rf"{lang['value']}\s*\+", lang["quote"]) else (lang["value"] if lang else None)) if lang else None,
            "integrations": cell(by("x.integrations") + stated, {"named": integ[:12], "more": max(0, len(integ) - 12),
                                  "stated": f"{stated[0]['value']:,}+" if stated and re.search(r"\+", stated[0]["quote"]) else (f"{stated[0]['value']:,}" if stated else None)}) if (integ or stated) else None,
            "compliance": cell(comp_src, sorted(compl)),
            "in_person": flag("x.in_person_capture"), "bot_free": flag("x.bot_free"), "free_plan": flag("x.free_plan"),
            "chrome_users": cell(chrome[:1], chrome[0]["value"]) if chrome else None,
            "chrome_rating": cell(rating("chromewebstore.google.com")[:1], rating("chromewebstore.google.com")[0]["value"]["rating"]) if rating("chromewebstore.google.com") else None,
            "appstore_rating": cell(rating("apps.apple.com")[:1], rating("apps.apple.com")[0]["value"]["rating"]) if rating("apps.apple.com") else None,
            "facts": sum(len(v) for v in f.values())}

CURRENCY = re.compile(r"[$€£¥]\s?\d|\d\s?(usd|eur|gbp)\b", re.I)

def find(F, e, metric, phrase):
    for x in F[e].get(metric, []):
        if norm(phrase) in norm(x["quote"]) and not CURRENCY.search(x["quote"]):          # no prices on screen, ever
            return {"quote": x["quote"], "url": x["url"], "host": host(x["url"]), "checked": x["checked"], "call": x["call"]}
    return None

def platform_rules(F, checked=None):
    checked = checked or max((x["checked"] for e in F for m in F[e] for x in F[e][m]), default="2026-11-04")
    """What each platform you may already pay for covers, as rules over verified quotes. None = no verified fact: unknown."""
    zp = find(F, "zoom", "x.notes_plans", "available with paid Zoom Workplace plans")
    zb = find(F, "zoom", "x.in_person_terms", "for 3 hosted meetings per month")
    zi = find(F, "zoom", "x.in_person_terms", "Transcribe in-person meetings (3 uses per month)")
    tm = find(F, "teams", "x.notes_plans", "You must assign a Teams Premium license or Microsoft Copilot license to your users")
    def r(status, why, src, changes):
        at = (src or {}).get("checked") or checked
        return {"status": status, "why": why, "source": src, "changesIf": changes, "evaluatedAt": at, "freshUntil": add_days(at + "T00:00:00Z", FRESH_DAYS)[:10]}
    unknown = lambda what: r("unknown", f"We haven't found a source that says {what}.", None, "A source states it either way.")
    zoom = {
        "Zoom Workplace Basic": {
            "online": r("limited", "Zoom Basic includes meeting summaries for 3 hosted meetings a month.", zb, "Zoom lifts the limit on Basic.") if zb else unknown("what Zoom Basic includes"),
            "in_person": r("limited", "Zoom lists in-person transcription at 3 uses a month.", zi, "Zoom lifts the in-person limit.") if zi else unknown("Zoom covers in-person meetings")},
        "Zoom Workplace paid plan": {
            "online": r("covered", "Zoom Workplace paid plans include AI meeting summaries and My Notes.", zp, "Zoom drops summaries from paid plans.") if zp else unknown("which Zoom plans include summaries"),
            "in_person": r("limited", "Zoom lists in-person transcription at 3 uses a month.", zi, "Zoom lifts the in-person limit.") if zi else unknown("Zoom covers in-person meetings")}}
    microsoft = {
        "Teams without Premium": {
            "online": r("unmet", "Teams' meeting recap needs a Teams Premium or Microsoft Copilot license.", tm, "You add Teams Premium or a Copilot license.") if tm else unknown("which Teams licenses include recap"),
            "in_person": unknown("Teams takes notes in in-person meetings")},
        "Teams Premium": {
            "online": r("covered", "Teams Premium includes intelligent meeting recap.", tm, "Microsoft moves recap out of Teams Premium.") if tm else unknown("which Teams licenses include recap"),
            "in_person": unknown("Teams takes notes in in-person meetings")},
        "Microsoft Copilot": {
            "online": r("covered", "A Microsoft Copilot license includes intelligent meeting recap.", tm, "Microsoft moves recap out of Copilot.") if tm else unknown("which Teams licenses include recap"),
            "in_person": unknown("Teams takes notes in in-person meetings")}}
    return {"Zoom": zoom, "Microsoft": microsoft}

def real_check(c, key, obs):
    """The date a page was last REALLY re-read (tools/verify_references.py --record), never earlier than the fact's own observation: a live answer must not show the replay clock as its check date."""
    r = c.execute("SELECT last_checked FROM sync_checks WHERE key=?", (key,)).fetchone()
    return max(day(obs), day(r[0]) if r and r[0] else "")

def platform_languages(F):
    """How many languages each platform's notes support, from verified facts only (None = not verified)."""
    out = {"Microsoft": None}
    c = sqlite3.connect(f"file:{DEMO}?mode=ro", uri=True)
    row = c.execute("SELECT value, url, observed_at FROM facts WHERE entity_id='meet' AND metric='supported_languages' ORDER BY id DESC LIMIT 1").fetchone()
    out["Google"] = {"count": len(json.loads(row[0])), "source": {"url": row[1], "host": host(row[1]), "checked": real_check(c, "meet.supported_languages", row[2])}} if row else None
    z = [x for x in F["zoom"].get("x.languages_count", [])]
    out["Zoom"] = {"count": z[0]["value"], "source": {"url": z[0]["url"], "host": host(z[0]["url"]), "checked": z[0]["checked"]}} if z else None
    return out

def google_online():
    """Google Meet's 'Take notes for me' in online meetings: the Meet row of Google's edition table (in data/airstack-demo.db)."""
    c = sqlite3.connect(f"file:{DEMO}?mode=ro", uri=True)
    row = c.execute("SELECT value, url, observed_at FROM facts WHERE entity_id='meet' AND metric='listed_editions' AND url LIKE '%13952129%' ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return {}
    plans, url, obs = json.loads(row[0]), row[1], row[2]
    src = {"quote": "Take notes for me", "url": url, "host": host(url), "checked": real_check(c, "meet.listed_editions", obs), "call": None}
    allp = ["Business Starter", "Business Standard", "Business Plus", "Enterprise Standard", "Enterprise Plus", "Frontline Plus", "Google AI Pro", "Google AI Ultra"]
    fresh = {"evaluatedAt": day(obs), "freshUntil": add_days(obs, FRESH_DAYS)[:10]}
    return {p: ({"status": "covered", "why": f"Meet's 'Take notes for me' is listed for {p}.", "source": src, "changesIf": f"Google drops it from {p}.", **fresh} if p in plans else
                {"status": "unmet", "why": f"Meet's 'Take notes for me' isn't listed for {p}.", "source": src, "changesIf": f"Google adds {p}.", **fresh}) for p in allp} | {
        "No Google plan": {"status": "unmet", "why": "Meet's 'Take notes for me' needs a Google Workspace or Google AI plan.", "source": src, "changesIf": "You move to a plan that includes it.", **fresh}}

PROFILE_LISTS = ("x.deployment", "x.platforms", "x.sdk_languages", "x.models_supported", "x.integrations", "x.plan_names")
# Projection rules: a quote proves the words are on the page, not what they mean.
DOWNLOAD_BUTTON = re.compile(r"^\W*download (for|on)\b", re.I)                     # "Download for macOS": the reader's OS, not the product's platforms
TRIAL = re.compile(r"\btrial\b|free for \d+\s*days|\d+[- ]day free|\bdays? free\b|\bcredits?\b|\btry (it )?(for )?free\b", re.I)
PENDING = re.compile(r"in progress|underway|pursuing|working towards?|in the process|planned|coming soon|expected|roadmap|on track", re.I)
FOOTNOTE = re.compile(r"^\s*[*†‡]")                                                 # "*Only Grok models are available on this plan"
MODEL_VENDORS = set(CFG["model_vendors"])
SDK_SCOPE = set()                                                                    # products whose SDK languages are a real field: the registry-tracked packages
HIDDEN = {}                                                                          # facts the projection rules kept off the profile, by field

def hide(m, why):
    HIDDEN.setdefault(m[2:], {}).setdefault(why, 0); HIDDEN[m[2:]][why] += 1

def shown(e, m, x):
    """Whether one verified fact may shape the profile's value for this field (it stays in the evidence chain either way)."""
    q = x["quote"]
    if FOOTNOTE.match(q): hide(m, "a footnote or plan restriction"); return False
    if m == "x.platforms" and DOWNLOAD_BUTTON.match(q): hide(m, "a download button for the reader's own system"); return False
    if m == "x.sdk_languages" and e not in SDK_SCOPE: hide(m, "not a published SDK: likely navigation text"); return False
    if m == "x.compliance" and PENDING.search(q): hide(m, "a certification in progress, not held"); return False
    if m == "x.founded_year" and not re.search(r"\bfound(ed|ing|ers?)\b", q, re.I): hide(m, "a product or project date, not a founding"); return False
    return True

def models(e, vals):
    """Model names only: no vendors, no the product itself, no "X models" when a version of X is listed, no duplicates."""
    out = []
    for v in (re.sub(r"\s+models?$", "", v, flags=re.I).strip() for v in vals):
        k = v.lower()
        if not v or k in MODEL_VENDORS or re.sub(r"[^a-z0-9]", "", k) == re.sub(r"[^a-z0-9]", "", e.lower()):
            hide("x.models_supported", "a vendor or the product's own name"); continue
        if k not in (o.lower() for o in out): out.append(v)
    keep = [v for v in out if not any(o.lower().startswith(v.lower() + " ") for o in out)]
    for _ in range(len(out) - len(keep)): hide("x.models_supported", "a model family also listed by version")
    return keep

def profile(e, F):
    """A product profile: every verified fact Muse extracted from the product's own pages, folded per metric, with its pages."""
    f = F.get(e)
    if not f:
        return None
    by = lambda m: [x for x in sorted(f.get(m, []), key=lambda x: (DESCRIPTION_RANK if m == "x.what_it_does" else KIND_RANK).get(x["kind"], 9)) if shown(e, m, x)]
    out = {}
    for m in PROFILE_LISTS:
        vals, used, seen = [], [], set()
        for x in by(m):
            hit = False
            for v in x["value"]:
                v = re.sub(r"\s+plan$", "", v.strip(), flags=re.I) if m == "x.plan_names" else v.strip()     # "Free Plan" and "Free" are one plan
                k = v.lower()
                if k and k not in seen:
                    seen.add(k); vals.append(v); hit = True
            if hit: used.append(x)
        if m == "x.models_supported": vals = models(e, vals)
        if vals: out[m[2:]] = cell(used, vals)
    comp, csrc = fold(by("x.compliance"), globals()["comp"])
    if comp: out["compliance"] = cell(csrc, sorted(comp))
    for m in ("x.what_it_does", "x.license", "x.pricing_basis", "x.customers_claimed"):
        xs = [x for x in by(m) if not CURRENCY.search(x["quote"])]
        if xs: out[m[2:]] = cell(xs[:1], xs[0]["quote"])
    if any(x["value"] is True for x in by("x.open_source")): out["open_source"] = cell([x for x in by("x.open_source") if x["value"] is True][:1], True)
    yes = [x for x in by("x.free_plan") if x["value"] is True and not TRIAL.search(x["quote"])]
    for x in by("x.free_plan"):
        if x["value"] is True and TRIAL.search(x["quote"]): hide("x.free_plan", "a trial or credits, not a free plan")
    if yes and not any(x["value"] is False for x in by("x.free_plan")): out["free_plan"] = cell(yes[:1], True)
    elif yes: hide("x.free_plan", "contradicted by another page: left unknown")
    for m in ("x.integrations_count", "x.founded_year"):
        xs = by(m)
        if xs: out[m[2:]] = cell(xs[:1], xs[0]["value"])
    if not out:
        return None                                                     # nothing left to show once the projection rules apply: not a researched profile
    out["facts"] = sum(len(v) for v in f.values())
    out["calls"] = len({x["call"] for v in f.values() for x in v})
    return out

def main():
    F, names, fleet = load()
    vendors = [vendor(e, F, names) for e in INCUMBENTS if e in F]
    shown = json.dumps([[v.get("what") and v["what"]["value"]] for v in vendors]) + json.dumps(platform_rules(F))
    assert not CURRENCY.search(shown), "a price would reach the screen"
    mv = movers()
    from airstack.catalog import entries as catalog_entries, public
    cataloged = catalog_entries()
    listed = json.loads(paths.DIRECTORY.read_text())["products"] if paths.DIRECTORY.exists() else []
    profiled = [r["id"] for r in (mv["rows"] if mv else [])] + [e["id"] for e in cataloged] + [p[0] for p in listed]   # registry tools, cataloged products and directory listings, researched the same way
    SDK_SCOPE.update(r["id"] for r in (mv["rows"] if mv else [])); HIDDEN.clear()
    profiles = {k: profile(k, F) for k in profiled if k in F and k not in INCUMBENTS}
    catalog = {e["id"]: {k: v for k, v in public(e).items() if k in ("vendor", "homepage", "pricing", "checked")} for e in cataloged}   # a cataloged product's checked links
    data = {"lane": "meeting-notes", "title": "Meeting notes", "vendors": vendors, "movers": mv, "profiles": {k: v for k, v in profiles.items() if v and k not in blocked_ids()}, "catalog": catalog,
            "platformLanguages": platform_languages(F),
            "platforms": {**platform_rules(F, max((x["checked"] for e in F for m in F[e] for x in F[e][m]), default="")), "Google": {p: {"online": v} for p, v in google_online().items()}},
            "hidden_by_rule": {k: dict(sorted(v.items())) for k, v in sorted(HIDDEN.items())},   # facts verified on their page but kept off the profile, and why
            "fleet": {**fleet, "pass_rate": round(fleet["passed"] / fleet["checked"], 3) if fleet["checked"] else None,
                      "checked_on": max((x["checked"] for e in F for m in F[e] for x in F[e][m]), default="")}}
    out = paths.MARKET_DATA                                   # what every page needs: each profile's fact count; the facts themselves load with a product's page
    out.write_text("// spec: AS-327 AS-328\n// GENERATED by backend/tools/build_market_data.py from data/airstack-market.db. Do not edit by hand.\n"
                   "window.AIRSTACK_MARKET = " + json.dumps({**data, "profiles": {k: {"facts": v["facts"]} for k, v in data["profiles"].items()}},
                                                            ensure_ascii=False, separators=(",", ":")) + ";\n")
    paths.PROFILES.write_text(json.dumps(data["profiles"], ensure_ascii=False, separators=(",", ":")))
    print(f"market-data.js: {len(vendors)} vendors, {fleet['facts']} facts, pass rate {data['fleet']['pass_rate']}, {fleet['calls']} extraction calls")
    return data

if __name__ == "__main__":
    main()
