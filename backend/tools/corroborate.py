# spec: AS-238 AS-334
"""Writes data/corroboration.json: each vendor claim the evidence chain shows, compared value for value with the vendor's own public
registry records (PyPI JSON, the npm registry, the GitHub repository API), plus independent records the vendor does not write (AS-334,
see `independent` below) and the chain's corroboration rate. Free and deterministic: no model, no key in code.

A registry entry or a GitHub repository is published by the SAME vendor as the page: a match is a second record from the same origin,
never independent confirmation, and it never reaches `agree_independent`. A registry value that contradicts the claim is kept as
agrees=false, never hidden. What a registry does not state is not observed and gets no record: a missing or unrecognised license is not
evidence of closed source, and one package's metadata does not list every SDK or platform, so sdk_languages and platforms can match or
stay silent but never disagree. "Operating System :: OS Independent" names no system and matches nothing.

Every response is saved to data/registry-raw/<sha1(url)>.json (PyPI and npm bodies cut to the fields used here; the envelope says which)
and the output is built FROM THOSE FILES, so `--offline` reproduces it byte for byte. GitHub is read through `gh api`, the gh CLI's own
login, as build_movers does: the unauthenticated API allows 60 requests an hour, fewer than the repositories listed.
The independent sources are read through airstack.fetch (robots.txt obeyed) and each run of each is ONE file,
data/<source>-records-raw/<day>.json.gz; the output uses the latest file of each.
Usage: python backend/tools/corroborate.py [--offline | --only registries|rdap|wikipedia|gdelt]"""
import argparse, gzip, json, pathlib, re, sys, time, urllib.parse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from build_movers import raw_path, dumps, Raw
from airstack.connectors import registries as reg
from airstack import paths
from airstack.fetch import host as url_host

UNIVERSE, RAW, OUT = paths.UNIVERSE, paths.DATA / "registry-raw", paths.DATA / "corroboration.json"
PYPI, NPM, GH_JQ = "https://pypi.org/pypi/{}/json", "https://registry.npmjs.org/{}/latest", "{full_name, html_url, language, license}"
KEEP = {"pypi.org": ("info", ("name", "version", "license", "license_expression", "classifiers", "requires_python")),   # "releases" alone is megabytes
        "registry.npmjs.org": (None, ("name", "version", "license", "licenses", "types", "typings", "exports", "os"))}
POLITE = {"pypi.org": 0.5, "registry.npmjs.org": 0.5, "api.github.com": 0.3}      # seconds before each request
METRICS = ("license", "open_source", "sdk_languages", "platforms")
SAME_ORIGIN = ("A package registry entry or GitHub repository is published by the same vendor as the page: a match is a second record "
               "from the same origin, not independent confirmation.")

LICENSES = [  # (SPDX id, pattern on the lowercased text). Every id is either in OSI or a known non-OSI license.
    ("AGPL-3.0", r"\bagpl|affero"),
    ("LGPL-3.0", r"\blgpl[- ]?v?3|lesser general public licen[cs]e v(?:ersion )?3"),
    ("LGPL-2.1", r"\blgpl[- ]?v?2|lesser general public licen[cs]e v(?:ersion )?2"),
    ("GPL-3.0", r"\bgpl[- ]?v?3|(?<!lesser )(?<!affero )general public licen[cs]e v(?:ersion )?3"),
    ("GPL-2.0", r"\bgpl[- ]?v?2|(?<!lesser )(?<!affero )general public licen[cs]e v(?:ersion )?2"),
    ("Apache-2.0", r"\bapache[\w\s,.-]{0,30}?\b2(?:\.0)?\b"),
    ("MPL-2.0", r"\bmpl[- ]?2|mozilla public licen[cs]e,? (?:v(?:ersion )?)?2"),
    ("BSD-3-Clause", r"\bbsd[- ]3|3-clause|new bsd|revised bsd|modified bsd"),
    ("BSD-2-Clause", r"\bbsd[- ]2\b|2-clause|simplified bsd"),
    ("MIT", r"\bmit\b"),
    ("ISC", r"\bisc\b"),
    ("Unlicense", r"\bunlicense\b"),
    ("BSL-1.0", r"\bbsl-1\.0|boost software licen"),
    ("SSPL-1.0", r"\bsspl|server side public licen"),
    ("BUSL-1.1", r"\bbusl|business source licen"),
    ("Elastic-2.0", r"\belastic(?:-2\.0| licen)"),
    ("Proprietary", r"\bproprietary\b|^unlicensed$"),     # npm's "UNLICENSED" means not licensed for use by others
]
FAMILIES = [("Apache", r"\bapache\b"), ("BSD", r"\bbsd\b")]   # "Apache Software License" and "BSD License" name no version
OSI = {"AGPL-3.0", "LGPL-3.0", "LGPL-2.1", "GPL-3.0", "GPL-2.0", "Apache-2.0", "Apache", "MPL-2.0", "BSD-3-Clause", "BSD-2-Clause", "BSD",
       "MIT", "ISC", "Unlicense", "BSL-1.0"}
NOT_THAT_LICENSE = re.compile(r"derivative|based on")            # "Apache-2.0-derivative license" is not Apache-2.0
LANG = {"js": "javascript", "node.js": "javascript", "nodejs": "javascript", "node": "javascript", "ts": "typescript", "golang": "go",
        "cpp": "c++", "csharp": "c#", ".net": "c#"}
OS = {"linux": "linux", "windows": "windows", "win32": "windows", "macos": "macos", "mac": "macos", "mac os": "macos", "osx": "macos",
      "os x": "macos", "darwin": "macos", "bsd": "bsd", "freebsd": "bsd", "openbsd": "bsd"}

# ---------------------------------------------------------------- normalisation (pure)

def spdx(text):
    """The SPDX ids a license text names. Empty when it names none we know: not observed, never a guess."""
    normalized = str(text or "").strip().lower()
    if not normalized or NOT_THAT_LICENSE.search(normalized):
        return frozenset()
    identifiers = {identifier for identifier, pattern in LICENSES if re.search(pattern, normalized)}
    families = {family for family, pattern in FAMILIES if re.search(pattern, normalized)
                and not any(identifier.startswith(family + "-") for identifier in identifiers)}
    return frozenset(identifiers | families)

def same_license(first, second):
    return first == second or first.startswith(second + "-") or second.startswith(first + "-")

def langs(text):
    normalized = re.sub(r"\(.*?\)", "", str(text)).strip().lower()
    return {LANG.get(part.strip(), part.strip()) for part in normalized.split("/") if part.strip()}

def claim_of(metric, value):
    """What a claim value says in registry terms, or None when no registry field can speak to it."""
    if metric == "license":
        ids = spdx(value)
        return next(iter(ids)) if len(ids) == 1 else None
    if metric == "open_source":
        return value if isinstance(value, bool) else None
    if metric == "sdk_languages":
        return langs(value) or None
    normalized = str(value).strip().lower()
    return {OS[normalized]} if metric == "platforms" and normalized in OS else None

# ---------------------------------------------------------------- what each registry states (pure, from one envelope)

def _base(source, url, env):
    err = env.get("error") or (None if env.get("body") is not None else "empty response")
    return {"source": source, "url": url, "checked": (env.get("fetched_at") or "")[:10] or None, "error": err,
            "license": (frozenset(), None), "languages": {}, "os": {}}

def pypi(pkg, env):
    record = _base("pypi", f"https://pypi.org/project/{pkg}/", env)
    if record["error"]:
        return record
    info = env["body"].get("info") or {}
    classifiers = info.get("classifiers") or []
    license_classifiers = [classifier for classifier in classifiers if classifier.startswith("License ::")]
    if info.get("license_expression"):
        record["license"] = (spdx(info["license_expression"]), f"license_expression: {info['license_expression']}")
    elif license_classifiers:
        record["license"] = (spdx(" ; ".join(classifier.split("::")[-1] for classifier in license_classifiers)),
                             "; ".join(license_classifiers))
    elif info.get("license") and len(info["license"]) <= 200:                # older packages paste the whole license text here
        record["license"] = (spdx(info["license"]), f"license: {info['license']}")
    for classifier in classifiers:
        if classifier.startswith("Programming Language ::"):
            for language in langs(classifier.split("::")[1]):
                record["languages"].setdefault(language, classifier)
        if classifier.startswith("Operating System ::"):
            for platform in ("linux", "windows", "macos", "bsd"):
                if platform in classifier.lower():
                    record["os"].setdefault(platform, classifier)
    if info.get("requires_python"):
        record["languages"].setdefault("python", f"requires_python: {info['requires_python']}")
    return record

def npm(pkg, env):
    record = _base("npm", f"https://www.npmjs.com/package/{pkg}", env)
    if record["error"]:
        return record
    metadata = env["body"]
    raw_license = metadata.get("license")
    raw_license = raw_license.get("type") if isinstance(raw_license, dict) else raw_license
    if not raw_license and isinstance(metadata.get("licenses"), list):
        raw_license = " OR ".join(str(item.get("type")) for item in metadata["licenses"] if isinstance(item, dict))
    if raw_license:
        record["license"] = (spdx(raw_license), f"license: {raw_license}")
    record["languages"]["javascript"] = f"npm package {metadata.get('name') or pkg}"
    typed = metadata.get("types") or metadata.get("typings")
    if typed or '"types"' in json.dumps(metadata.get("exports") or {}):
        record["languages"]["typescript"] = f"types: {typed}" if typed else "exports declare types"
    for platform in metadata.get("os") or []:
        if platform in OS:
            record["os"].setdefault(OS[platform], f"os: {', '.join(metadata['os'])}")
    return record

def github(repo, env):
    body = env.get("body") or {}
    record = _base("github", body.get("html_url") or f"https://github.com/{repo}", env)
    if record["error"]:
        return record
    identifier = (body.get("license") or {}).get("spdx_id")
    if identifier and identifier != "NOASSERTION":                         # GitHub found a license it cannot name
        record["license"] = (spdx(identifier), f"license.spdx_id: {identifier}")
    for language in langs(body["language"]) if body.get("language") else ():
        record["languages"][language] = f"language: {body['language']}"
    return record

def compare(metric, claim, record):
    """One registry's record for one claim value, or None when that registry does not state it."""
    base = {"source": record["source"], "url": record["url"], "checked": record["checked"]}
    ids, raw = record["license"]
    if metric in ("license", "open_source"):
        if not ids:
            return None
        named = " OR ".join(sorted(ids))
        if metric == "license":
            return {**base, "claim": claim, "registry_value": named, "raw": raw, "agrees": any(same_license(claim, i) for i in ids)}
        osi = bool(ids & OSI)
        return {**base, "claim": claim, "registry_value": named + (" (OSI-approved)" if osi else " (not OSI-approved)"), "raw": raw, "agrees": osi == claim}
    shown = record["languages"] if metric == "sdk_languages" else record["os"]
    hit = sorted(claim & shown.keys())
    return {**base, "claim": hit[0], "registry_value": hit[0], "raw": shown[hit[0]], "agrees": True} if hit else None

# ---------------------------------------------------------------- the dataset

def registries(tool, fetch, run):
    out = [pypi(p, fetch(PYPI.format(p))) for p in tool.get("pypi") or []] + [npm(p, fetch(NPM.format(p))) for p in tool.get("npm") or []]
    return out + ([github(tool["github"], run(f"repos/{tool['github']}", GH_JQ))] if tool.get("github") else [])

def build(universe, entities, fetch, run, second=None):
    """Pure given the fetchers. entities: the chain's {id: {"facts": [{"metric", "value"}]}} (today's rules already applied).
    second: the latest saved run of each independent source ({source: batch or None}); None leaves them out."""
    stamps = [envelope["fetched_at"] for batch in (second or {}).values() if batch
              for envelope in batch["responses"].values()]
    def tracked_fetch(url):
        envelope = fetch(url)
        stamps.append(envelope.get("fetched_at") or "")
        return envelope
    def tracked_run(path, jq):
        envelope = run(path, jq)
        stamps.append(envelope.get("fetched_at") or "")
        return envelope
    registry_records = {tool["id"]: registries(tool, tracked_fetch, tracked_run) for tool in universe}
    successful = {tool_id: [record for record in records if not record["error"]]
                  for tool_id, records in registry_records.items()}
    by_metric, claims, seen = {m: Counter() for m in METRICS}, [], set()
    for tool_id in sorted(entities):
        for fact in entities[tool_id]["facts"]:
            metric = fact["metric"]
            if metric not in METRICS:
                continue
            for value in fact["value"] if isinstance(fact["value"], list) else [fact["value"]]:
                identity = (tool_id, metric, json.dumps(value, sort_keys=True))
                if identity in seen:
                    continue
                seen.add(identity)
                counters, normalized_claim = by_metric[metric], claim_of(metric, value)
                counters["claims"] += 1
                comparisons = [comparison for record in successful.get(tool_id, [])
                               if normalized_claim is not None and (comparison := compare(metric, normalized_claim, record))]
                counters["not_comparable" if normalized_claim is None else "with_twin" if comparisons else "no_twin"] += 1
                if comparisons:
                    counters["disagreeing" if any(not comparison["agrees"] for comparison in comparisons) else "agreeing"] += 1
                    claims.append({"tool": tool_id, "metric": metric, "value": value, "registry": comparisons})
    keys = ("claims", "with_twin", "agreeing", "disagreeing", "no_twin", "not_comparable")
    no_registry = {tool_id: "no PyPI or npm package and no GitHub repository listed in data/universe.json"
                   for tool_id, records in registry_records.items() if not records}
    no_registry |= {tool_id: "every registry read failed" for tool_id, records in registry_records.items()
                    if records and not successful[tool_id]}
    no_registry |= {tool_id: "not in data/universe.json" for tool_id in entities if tool_id not in registry_records}
    claims.sort(key=lambda item: (item["tool"], item["metric"], json.dumps(item["value"], sort_keys=True)))
    return {"generated_at": max(stamps) if stamps else None, "note": SAME_ORIGIN, "rates": rates(entities, claims),
            **({"independent": independent(second)} if second is not None else {}),
            "rules": {"license": "both sides normalised to SPDX; a claim naming no single license is not comparable; GitHub NOASSERTION, "
                                 "npm 'SEE LICENSE IN ...' and unknown names are not observed",
                      "open_source": "agrees when the registry names an OSI-approved license; disagrees when it names only non-OSI licenses",
                      "sdk_languages": "agrees when a registry shows the language (PyPI 'Programming Language ::' or requires_python, npm "
                                       "package = JavaScript, npm types = TypeScript, GitHub primary language); never disagrees",
                      "platforms": "agrees when PyPI 'Operating System ::' or npm 'os' names the system; never disagrees"},
            "summary": {"totals": {key: sum(counters[key] for counters in by_metric.values()) for key in keys},
                        "by_metric": {metric: {key: counters[key] for key in keys} for metric, counters in by_metric.items()}},
            "no_registry": dict(sorted(no_registry.items())),
            "failures": [{"tool": tool_id, "source": record["source"], "url": record["url"], "error": record["error"]}
                         for tool_id, records in registry_records.items() for record in records if record["error"]],
            "claims": claims}

def rates(entities, claims):
    """Each fact the chain shows, in exactly one class. Corroborated needs an independent source stating the same value (today only
    another page from a host known to be independent: the chain's agree_independent); the vendor's other pages and its registry
    entries are a second record from the same origin; a registry value that contradicts the claim makes it disputed."""
    registry_by_claim = {(claim["tool"], claim["metric"], json.dumps(claim["value"], sort_keys=True)): claim["registry"]
                         for claim in claims}
    totals = Counter({key: 0 for key in ("facts", "corroborated", "disputed", "second_record", "single_record")})
    corroborated = []
    for tool_id in sorted(entities):
        for fact in entities[tool_id]["facts"]:
            values = fact["value"] if isinstance(fact["value"], list) else [fact["value"]]
            records = [record for value in values
                       for record in registry_by_claim.get((tool_id, fact["metric"], json.dumps(value, sort_keys=True)), [])]
            totals["facts"] += 1
            classification = ("disputed" if any(not record["agrees"] for record in records)
                              else "corroborated" if fact.get("agree_independent")
                              else "second_record" if fact.get("agree") or records else "single_record")
            totals[classification] += 1
            if classification == "corroborated":
                corroborated.append({"tool": tool_id, "metric": fact["metric"], "value": fact["value"], "url": fact.get("url"),
                                     "independent_hosts": fact["agree_independent"]})
    return {**totals, "corroborated_rate": round(totals["corroborated"] / totals["facts"], 4) if totals["facts"] else None,
            "corroborated_facts": corroborated,
            "labels": {"corroborated": "an independent source states the same value", "disputed": "a registry record states a different value",
                       "second_record": "a second record from the same origin (another vendor page or its own registry entry)",
                       "single_record": "one record only"},
            "note": "The independent records below (domain registration, Wikipedia pageviews, news volume) state no value a fact claims, "
                    "so they corroborate and dispute nothing: they are context."}

# ---------------------------------------------------------------- independent records (AS-334)
# Only what a platform measures itself counts as independent: a registry's registration date, Wikimedia's pageview counts, GDELT's
# article counts. Text a vendor writes on a store or a registry does not. Each source's terms were read before it was used (EXCLUDED
# lists what was dropped and why). Unknown is a null value with its reason, never zero.

SECOND = ("rdap", "wikipedia", "gdelt")
IANA_RDAP = "https://data.iana.org/rdap/dns.json"
ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{}.json"
PAGEVIEWS = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{}/monthly/{}/{}"
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc?"
PAUSE = {"rdap": 1.0, "wikipedia": 0.3, "gdelt": 6.0}       # seconds before each request; GDELT asks for one request every 5 seconds
SHARED_HOSTS = {"github.com", "github.io", "gitlab.com", "readthedocs.io", "vercel.app", "netlify.app", "pages.dev", "huggingface.co"}
RDAP_TERMS = {   # registry RDAP host -> its terms, read 2026-11-05: lawful, query-based lookups; no spam, no high-volume automated processes
    "rdap.verisign.com": "https://www.verisign.com/legal-center/rdap-terms/",
    "rdap.identitydigital.services": "https://www.identity.digital/policies/rdds-access-policy",
    "rdap.publicinterestregistry.org": "https://thenew.org/org-people/about-pir/policies/"}
EXCLUDED = {
    "App Store and iTunes Search": "Apple's terms bar automated reading (airstack.fetch.TERMS_EXCLUDED).",
    "Visual Studio Marketplace": "Its Terms of Use allow information to be obtained only through Microsoft's publicly supported interfaces and prohibit "
                                 "harvesting, spidering or scraping 'whether automated or not'; robots.txt disallows /_apis/. "
                                 "https://cdn.vsassets.io/v/M264_20251020.18/_content/Microsoft-Visual-Studio-Marketplace-Terms-of-Use.pdf (read 2026-11-05)",
    "Docker Hub": "Its Terms of Use (effective 2026-08-26) grant access 'for internal purposes' only; republishing pull counts is not granted. "
                  "https://www.docker.com/legal/docker-terms-use/ (read 2026-11-05)",
    "pubapi.registry.google": "Google Registry's RDAP terms (.dev, .app, .google, .new): 'Do not compile, repackage, disseminate, or otherwise use the "
                              "information ... in its entirety, or in any substantial portion, without our prior written permission.' "
                              "https://www.registry.google/policies/rdap-terms/ (read 2026-11-05)"}
SOURCES = {
    "rdap": {"name": "RDAP, from the registry IANA lists for the domain's TLD", "url": IANA_RDAP, "kind": "registration",
             "measures": "the date the vendor's domain was first registered, as its registry records it",
             "terms": RDAP_TERMS, "license": "registry terms per registry (see terms); a registration date only, no contact data kept",
             "note": "A domain can be registered before or after a company or product starts: it neither confirms nor disputes a founding year."},
    "wikipedia": {"name": "Wikimedia pageviews API (English Wikipedia)", "url": "https://wikimedia.org/api/rest_v1/", "kind": "attention",
                  "measures": "views of the product's English Wikipedia article by people (agent=user), over the twelve complete months before the read",
                  "license": "CC0-1.0", "license_url": "https://dumps.wikimedia.org/legal.html",
                  "article_from": "Wikidata (CC0-1.0): the item whose official website host and English label match the product, then its enwiki sitelink",
                  "note": "Attention, not adoption: how often people read about it, not how many use it."},
    "gdelt": {"name": "The GDELT Project, DOC 2.0 API", "url": "https://www.gdeltproject.org/", "kind": "attention",
              "measures": "news articles GDELT monitored in the last three months that match the product's curated query",
              "license": "GDELT terms: unlimited use; any use or redistribution must cite the GDELT Project and link https://www.gdeltproject.org/",
              "note": "Attention, not adoption. Only products with a curated query (hn_query in data/universe.json) are asked: a bare product name "
                      "would count every other meaning of the word, and a query can still catch some."}}

def vendor_domain(host):
    """The registered domain of a homepage host; None on a shared host (github.com is GitHub's domain, not the vendor's)."""
    labels = host.split(".")
    has_compound_suffix = len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in ("co", "com", "org", "net", "ac", "gov")
    domain = ".".join(labels[-3:] if has_compound_suffix else labels[-2:])
    return None if domain in SHARED_HOSTS or host in SHARED_HOSTS else domain

def pageviews_url(title, window):
    return PAGEVIEWS.format(urllib.parse.quote(title.replace(" ", "_"), safe=""), *window)

def gdelt_url(query):
    return GDELT + urllib.parse.urlencode({"query": query, "mode": "timelinevolraw", "format": "json", "timespan": "3months"})

def _none(reason, **extra):
    return {"value": None, "reason": reason, **extra}

def _failed(env):
    return env is None or env.get("error") or env.get("body") is None

def _rdap(target, responses):
    if not target.get("url"):
        return _none(target["reason"], domain=target.get("domain"))
    envelope = responses.get(target["url"])
    if _failed(envelope):
        return _none(f"the registry read failed ({(envelope or {}).get('error') or 'not saved'})",
                     domain=target["domain"], url=target["url"])
    dates = [event["eventDate"][:10] for event in envelope["body"].get("events") or []
             if event.get("eventAction") == "registration" and event.get("eventDate")]
    if not dates:
        return _none("the registry record has no registration date", domain=target["domain"], url=target["url"])
    return {"value": dates[0], "domain": target["domain"], "registry": url_host(target["url"]), "url": target["url"],
            "checked": envelope["fetched_at"][:10]}

def _wikipedia(target, responses, window):
    if not target.get("qid"):
        return _none(target["reason"])
    wikidata = f"https://www.wikidata.org/wiki/{target['qid']}"
    envelope = responses.get(ENTITY.format(target["qid"]))
    if _failed(envelope):
        return _none(f"the Wikidata read failed ({(envelope or {}).get('error') or 'not saved'})", wikidata=wikidata)
    title = envelope["body"].get("enwiki")
    if not title:
        return _none("Wikidata lists no English Wikipedia article", wikidata=wikidata)
    if envelope["body"].get("redirect"):
        return _none("the English Wikipedia sitelink is a redirect, so its views are not the article's", article=title, wikidata=wikidata)
    api = pageviews_url(title, window)
    pageviews = responses.get(api)
    items = [] if _failed(pageviews) else pageviews["body"].get("items") or []
    if not items:
        return _none(f"no pageview data for the article ({(pageviews or {}).get('error') or 'empty'})",
                     article=title, wikidata=wikidata, api=api)
    return {"value": sum(item["views"] for item in items), "monthly": [item["views"] for item in items], "months": len(items),
            "from": items[0]["timestamp"][:4] + "-" + items[0]["timestamp"][4:6], "to": items[-1]["timestamp"][:4] + "-" + items[-1]["timestamp"][4:6],
            "article": title, "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
            "wikidata": wikidata, "api": api, "checked": pageviews["fetched_at"][:10]}

def _gdelt(target, responses):
    if not target.get("query"):
        return _none(target["reason"])
    url = gdelt_url(target["query"])
    envelope = responses.get(url)
    timeline = [] if _failed(envelope) else envelope["body"].get("timeline") or []
    if not timeline:
        return _none(f"GDELT returned no timeline ({(envelope or {}).get('error') or 'empty answer'}): not observed, not zero",
                     query=target["query"], api=url)
    return {"value": sum(day["value"] for day in timeline), "days": len(timeline),
            "from": timeline[0]["date"][:8], "to": timeline[-1]["date"][:8], "query": target["query"],
            "api": url, "checked": envelope["fetched_at"][:10]}

def independent(second):
    """{source: latest saved run or None} -> the per-tool records, the coverage, and where each came from. Pure."""
    tools = defaultdict(dict)
    readers = (("rdap", "domain_registered", lambda target, batch: _rdap(target, batch["responses"])),
               ("wikipedia", "wikipedia_views", lambda target, batch: _wikipedia(target, batch["responses"], batch["window"])),
               ("gdelt", "news_articles", lambda target, batch: _gdelt(target, batch["responses"])))
    for source, field, read in readers:
        batch = second.get(source)
        for tool_id, target in sorted((batch or {}).get("targets", {}).items()):
            tools[tool_id][field] = read(target, batch)
    fields = ("domain_registered", "wikipedia_views", "news_articles")
    for record in tools.values():
        for field in fields:
            record.setdefault(field, _none("not read yet"))
    return {"sources": {source: {**SOURCES[source], "read": (second.get(source) or {}).get("run")} for source in SECOND},
            "excluded": EXCLUDED,
            "coverage": {"tools": len(tools),
                         **{field: sum(record[field]["value"] is not None for record in tools.values()) for field in fields}},
            "tools": dict(sorted(tools.items()))}

def wikidata_items(raw_dir=paths.DATA / "wikidata-raw"):
    """(official-site host, lowercased English label) -> Wikidata item ids, from the responses build_directory saved (CC0)."""
    items_by_identity = defaultdict(set)
    for raw_file in sorted(pathlib.Path(raw_dir).glob("*.json.gz")):
        payload = json.loads(gzip.decompress(raw_file.read_bytes()))
        results = payload.get("results") if isinstance(payload, dict) else None
        for result in results if isinstance(results, list) else []:
            subject, site, name = ((result.get(field) or {}).get("value") for field in ("s", "site", "name"))
            if subject and site and name:
                items_by_identity[(url_host(site), name.lower())].add(subject.rsplit("/", 1)[-1])
    return items_by_identity

def tools_of(universe, catalog):
    """id -> (name, homepage host, curated news query or None): the universe first, then the catalog."""
    tools = {tool["id"]: (tool["name"], url_host(tool["homepage"]), tool.get("hn_query")) for tool in universe}
    for product in catalog:
        host = (product.get("domain") or url_host(product.get("homepage"))).lower().removeprefix("www.")
        tools.setdefault(product["id"], (product["name"], host, None))
    return tools

def _enwiki(entity):
    """A Wikidata item cut to its English Wikipedia sitelink. A sitelink badged as a redirect is not the article: its views are not the article's."""
    sitelink = (entity.get("sitelinks") or {}).get("enwiki") or {}
    redirect_badges = {"Q70893996", "Q70894304"}
    return {"id": entity["id"], "enwiki": sitelink.get("title"), "redirect": bool(set(sitelink.get("badges") or ()) & redirect_badges)}

def _env(get, url, accept, keep, timeout=25):
    """One GET through airstack.fetch as an envelope; `keep` cuts the parsed body to what is read."""
    status, body, response_headers = get(url, {"Accept": accept}, timeout=timeout)
    envelope = {"url": url, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": status,
                "body": None, "error": None}
    if status != 200:
        envelope["error"] = ("robots.txt disallows" if response_headers.get("x-robots")
                             else "terms exclude" if response_headers.get("x-terms")
                             else f"HTTP {status}" if status else "no response")
        return envelope
    try:
        envelope["body"] = keep(json.loads(body))
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        envelope["error"] = "not the expected JSON: " + re.sub(r"\s+", " ", body[:160])
    return envelope

CUT = {"bootstrap": lambda body: {"publication": body.get("publication"), "services": body["services"]},
       "rdap": lambda body: {
           "ldhName": body.get("ldhName"),
           "events": [{field: event.get(field) for field in ("eventAction", "eventDate")} for event in body.get("events") or []],
           "terms": [link.get("href") for notice in body.get("notices") or [] for link in notice.get("links") or []
                     if link.get("rel") == "terms-of-service"]},
       "entity": lambda body: _enwiki(next(iter(body["entities"].values()))),
       "pageviews": lambda body: {"items": [{"timestamp": item["timestamp"], "views": item["views"]} for item in body["items"]]},
       "gdelt": lambda body: {"timeline": [{"date": day["date"], "value": day["value"]}
                                            for day in (body.get("timeline") or [{}])[0].get("data") or []]}}

def read_second(source, universe, catalog, today, get, sleep=time.sleep, wikidata=None):
    """Read one independent source for every tool and return the run as one batch: {source, run, targets, responses[, window]}.
    Targets are decided here and saved with the run, so the build never re-derives them."""
    tools, responses = tools_of(universe, catalog), {}
    def fetch(url, accept, keep, timeout=25):
        if url not in responses:
            sleep(PAUSE[source])
            responses[url] = _env(get, url, accept, CUT[keep], timeout)
        return responses[url]
    batch = {"source": source, "run": today.isoformat(), "targets": {}, "responses": responses}
    if source == "rdap":
        bootstrap = fetch(IANA_RDAP, "application/json", "bootstrap")
        registry_by_tld = {} if _failed(bootstrap) else {
            tld: next((url for url in urls if url.startswith("https://")), None)
            for tlds, urls in bootstrap["body"]["services"] for tld in tlds}
        for tool_id, (_, host, _query) in sorted(tools.items()):
            domain = vendor_domain(host)
            registry = registry_by_tld.get(domain.rsplit(".", 1)[-1]) if domain else None
            if not domain:
                reason = "the homepage is on a shared host, not the vendor's own domain"
            elif not registry:
                reason = f"IANA lists no RDAP service for .{domain.rsplit('.', 1)[-1]}"
            elif url_host(registry) in EXCLUDED:
                reason = f"{url_host(registry)}: its terms bar republishing (see excluded)"
            elif url_host(registry) not in RDAP_TERMS:
                reason = f"{url_host(registry)}: terms not reviewed, so not read"
            else:
                batch["targets"][tool_id] = {"domain": domain, "url": registry.rstrip("/") + "/domain/" + domain}
                fetch(batch["targets"][tool_id]["url"], "application/rdap+json", "rdap")
                continue
            batch["targets"][tool_id] = {"domain": domain, "reason": reason}
    elif source == "wikipedia":
        first = date(today.year, today.month, 1)
        start = date(first.year - 1, first.month, 1)
        batch["window"] = [start.strftime("%Y%m%d"), date.fromordinal(first.toordinal() - 1).strftime("%Y%m%d")]
        wikidata_index = wikidata if wikidata is not None else wikidata_items()
        for tool_id, (name, host, _query) in sorted(tools.items()):
            candidates = wikidata_index.get((host, name.lower()), set())
            if len(candidates) != 1:
                batch["targets"][tool_id] = {
                    "reason": "no single Wikidata item has this product's homepage host and English name" if not candidates
                    else f"{len(candidates)} Wikidata items share this product's homepage host and English name"}
                continue
            batch["targets"][tool_id] = {"qid": next(iter(candidates)), "matched_by": "official website host and English label"}
            envelope = fetch(ENTITY.format(batch["targets"][tool_id]["qid"]), "application/json", "entity")
            if not _failed(envelope) and envelope["body"]["enwiki"] and not envelope["body"]["redirect"]:
                fetch(pageviews_url(envelope["body"]["enwiki"], batch["window"]), "application/json", "pageviews")
    elif source == "gdelt":
        for tool_id, (_, _host, query) in sorted(tools.items()):
            batch["targets"][tool_id] = {"query": query} if query else {"reason": "no curated news query (hn_query in data/universe.json)"}
            if query:
                fetch(gdelt_url(query), "application/json", "gdelt", timeout=60)
    return batch

def second_path(source, day, root=paths.DATA):
    return pathlib.Path(root) / f"{source}-records-raw" / f"{day}.json.gz"

def save_second(batch, root=paths.DATA):
    path = second_path(batch["source"], batch["run"], root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(batch, ensure_ascii=False, sort_keys=True).encode(), mtime=0))
    return path

def load_second(root=paths.DATA):
    """{source: the latest saved run, or None when the source was never read}."""
    latest = {}
    for source in SECOND:
        runs = sorted((pathlib.Path(root) / f"{source}-records-raw").glob("????-??-??.json.gz"))
        latest[source] = json.loads(gzip.decompress(runs[-1].read_bytes())) if runs else None
    return latest

# ---------------------------------------------------------------- fetch, save, replay

def project(env):
    """Keep only the fields read above (the envelope records the cut, as gh_run records its jq filter)."""
    keep = KEEP.get(urllib.parse.urlsplit(env["url"]).hostname)
    if not keep or not isinstance(env.get("body"), dict):
        return env
    sub, fields = keep
    src = (env["body"].get(sub) or {}) if sub else env["body"]
    kept = {k: src[k] for k in fields if k in src}
    return {**env, "body": {sub: kept} if sub else kept, "projection": (f"{sub}." if sub else "") + "{" + ", ".join(fields) + "}"}

def recording(raw_dir=RAW, sleep=time.sleep):
    raw_dir = pathlib.Path(raw_dir); raw_dir.mkdir(parents=True, exist_ok=True)
    def save(env):
        raw_path(env["url"], raw_dir).write_text(json.dumps(env, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        return env
    def fetch(url):
        sleep(POLITE.get(urllib.parse.urlsplit(url).hostname, 0.5))
        return save(project(reg.http_fetch(url, sleep=sleep)))
    def run(path, jq):
        sleep(POLITE["api.github.com"])
        return save(reg.gh_run(path, jq, sleep=sleep))
    return fetch, run

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="rebuild data/corroboration.json purely from the saved responses")
    parser.add_argument("--only", choices=("registries",) + SECOND, help="read only this source; the others come from their saved runs")
    options = parser.parse_args(argv)
    import build_chain_data
    from airstack.fetch import get
    universe = json.loads(UNIVERSE.read_text())
    entities = build_chain_data.build(corroboration={})["entities"]          # exactly the claims the chain shows; the database is read-only
    if not options.offline and options.only in (None, "registries"):
        build(universe, entities, *recording(RAW))                           # fetch + save every response
    for source in SECOND if not options.offline and options.only in (None, *SECOND) else ():
        if options.only in (None, source):
            batch = read_second(source, universe, json.loads(paths.CATALOG.read_text()), datetime.now(timezone.utc).date(), get)
            print("saved", save_second(batch))
    raw = Raw(RAW)
    output = build(universe, entities, raw.fetch, raw.run, load_second())   # the output always comes from the saved files
    if not options.offline and options.only in (None, "registries"):
        for path in RAW.glob("*.json"):
            if path.name not in raw.used:
                path.unlink()
    OUT.write_text(dumps(output))
    totals = output["summary"]["totals"]
    corroboration = output["rates"]
    coverage = output["independent"]["coverage"]
    print(f"wrote {OUT.relative_to(paths.ROOT)}: {totals['claims']} claim values, {totals['with_twin']} with a registry twin "
          f"({totals['agreeing']} agree, {totals['disagreeing']} disagree), {len(output['no_registry'])} tools with no registry record, "
          f"{len(output['failures'])} failed reads; {corroboration['corroborated']} of {corroboration['facts']} facts corroborated by an "
          f"independent source; independent records for {coverage['tools']} tools: {coverage['domain_registered']} domain registrations, "
          f"{coverage['wikipedia_views']} Wikipedia pageview counts, {coverage['news_articles']} news volumes")
    return 0

if __name__ == "__main__":
    sys.exit(main())
