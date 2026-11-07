# spec: AS-288
"""Trust for what you would install. For each package AirStack can tie to a tracked tool or an open-source candidate: the version a
fresh install gets, the OSV records that affect exactly that version (OpenSSF's package reports, the MAL- records, among them), and
whether npm holds a publish attestation for it. No model call, no key, no cost; nothing here downloads or runs a project's code.

Where packages come from. A tracked tool's are named in data/universe.json. An open-source candidate's (oss.json) are read from its
root package.json and kept only when npm's record for that name points back to the same repository: a name alone can belong to
someone else. deps.dev, the usual resolver, closes its API to automated readers in robots.txt, so it is not read; a candidate's
Python packages are not resolved, because PyPI's JSON API (which names a package's repository) is closed by robots.txt too.
Unresolved stays unresolved, with its reason.

What the words mean. Every check names the version it covered; a later release is not covered. "Reported" comes only from an OSV
record that is a MAL- package report, with its link. "No matching advisories found on <date>" says OSV had no record for that version
that day, nothing more. Provenance is npm's record of an attestation; AirStack does not re-verify its signature. PyPI's attestation
API is closed by robots.txt, so PyPI provenance is "not checked".

Every response of a run is saved in one file, data/trust-raw/<date>.json.gz, kept as the fields the build reads (so no personal
field such as a maintainer's email, and no signature bundle, is stored); trust.json is rebuilt from it offline, byte for byte.

Usage:  .venv/bin/python backend/tools/build_trust.py --fetch    # read npm, PyPI's release feeds, GitHub and OSV; save the run; build
        .venv/bin/python backend/tools/build_trust.py            # rebuild trust.json from the newest saved run"""
import argparse, gzip, json, pathlib, re, time, urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree
from airstack import paths

ROOT = paths.ROOT
from airstack import fetch                                               # one honest name; robots.txt obeyed (AS-274)

RAW, OUT = paths.DATA / "trust-raw", paths.TRUST
NPM, OSV = "https://registry.npmjs.org/", "https://api.osv.dev/v1/"
CLOSED = {"deps.dev": "https://api.deps.dev/v3/", "pypi-integrity": "https://pypi.org/integrity/", "pypi-json": "https://pypi.org/pypi/pip/json"}
ECOSYSTEM = {"npm": "npm", "pypi": "PyPI"}
SOURCES = {"GHSA": ("GitHub Advisory Database", "CC-BY-4.0"), "PYSEC": ("PyPI Advisory Database", "CC-BY-4.0"),
           "PSF": ("Python Software Foundation Database", "CC-BY-4.0"), "MAL": ("OpenSSF Malicious Packages", "Apache-2.0")}
PREDICATES = {"https://slsa.dev/provenance/v1": "SLSA provenance v1", "https://github.com/npm/attestation/tree/main/specs/publish/v0.1": "npm publish attestation"}
KEPT = {"npm version": "name, version, repository", "package.json": "name, private, repository", "attestations": "each attestation's predicateType",
        "release feed": "each item's title and pubDate", "osv querybatch": "whole",
        "osv record": "id, aliases, published, modified, withdrawn, severity, affected, database_specific.severity", "universe": "id, npm, pypi, github"}
FINAL = re.compile(r"\d+(\.\d+)*(\.post\d+)?")                         # a PEP 440 final release: no a, b, rc or dev
GH = re.compile(r"(?:git\+)?(?:(?:https?|ssh|git)://(?:git@)?github\.com/|git@github\.com:|github:)?([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/#?].*)?", re.I)
pick = lambda *keys: (lambda b: {k: b.get(k) for k in keys})

def gh_repo(repository):
    """owner/repo (lower case) from a package's repository field, or None when it names no GitHub repository."""
    u = repository.get("url") if isinstance(repository, dict) else repository
    m = GH.fullmatch((u or "").strip()) if isinstance(u, str) else None
    return f"{m[1]}/{m[2]}".lower() if m else None

def feed(text):
    return [[i.findtext("title"), i.findtext("pubDate")] for i in fetch.parse_xml(text).iter("item")]

def osv_record(b):
    return {k: b.get(k) for k in ("id", "aliases", "published", "modified", "withdrawn", "severity", "affected")} | \
           {"database_severity": (b.get("database_specific") or {}).get("severity")}

# ------------------------------------------------------------------ one source of answers: live (recording) or a saved run

def key(url, data=None):
    return url if data is None else f"POST {url} {data}"

def live(saved, sleep=0.2):
    def src(url, keep=lambda b: b, data=None):
        k = key(url, data)
        if k not in saved:
            s, text, h = fetch.get(url, data=data and data.encode(), headers={"Content-Type": "application/json"} if data else None)
            body = None
            if s == 200:
                try:
                    body = keep(json.loads(text) if text.lstrip()[:1] in "{[" else text)
                except (ValueError, ElementTree.ParseError, AttributeError):
                    s = "unreadable"
            saved[k] = {"status": s, "body": body, **({"closed": "robots.txt"} if "x-robots" in h else {})}
            time.sleep(sleep)
        return saved[k]
    src.saved = saved
    return src

def replay(saved):
    src = lambda url, keep=None, data=None: saved.get(key(url, data))
    src.saved = saved
    return src

def osv_answers(saved):
    """OSV's answer for each (ecosystem, name, version) it was asked about, read from the questions themselves: an answer is never
    moved to another version of the same package."""
    out, head = {}, f"POST {OSV}querybatch "
    for k, r in saved.items():
        if k.startswith(head):
            qs = json.loads(k[len(head):])["queries"]
            results = r["body"].get("results") if r["status"] == 200 and r["body"] else None
            for q, res in zip(qs, results or [None] * len(qs)):
                out[(q["package"]["ecosystem"], q["package"]["name"], q["version"])] = (res, r)
    return out

def why(r, what):
    """Why an answer is missing, in plain words."""
    if r is None:
        return f"{what} was not read in this run"
    if r.get("closed"):
        return f"{what} is closed to automated readers by robots.txt"
    return {404: f"{what} has no such entry", 0: f"{what} did not answer"}.get(r["status"], f"{what} answered {r['status']}")

# ------------------------------------------------------------------ resolving packages and versions

def npm_latest(src, name):
    return src(f"{NPM}{urllib.parse.quote(name, safe='@')}/latest", pick("name", "version", "repository"))

def version(src, system, name):
    """(version, published, how, None) for what a fresh install gets, or (None, None, None, reason)."""
    if system == "npm":
        r = npm_latest(src, name)
        if not r or r["status"] != 200 or not (r["body"] or {}).get("version"):
            return None, None, None, why(r, "npm's registry")
        return r["body"]["version"], None, "npm's dist-tag latest", None
    r = src(f"https://pypi.org/rss/project/{name}/releases.xml", feed)
    if not r or r["status"] != 200:
        return None, None, None, why(r, "PyPI's release feed")
    final = [(t, d) for t, d in r["body"] if t and FINAL.fullmatch(t)]
    if not final:
        return None, None, None, "PyPI's release feed lists no final release among its most recent"
    t, d = max(final, key=lambda td: [int(x) for x in re.findall(r"\d+", td[0])])
    return t, parsedate_to_datetime(d).date().isoformat() if d else None, "the highest final release in PyPI's release feed", None

def repo_packages(src, repo, declared):
    """The packages an open-source candidate publishes, with how that is known, or None and the reason."""
    if repo.lower() in declared:
        return declared[repo.lower()], "named in AirStack's tracked-tool list (data/universe.json)", None
    r = src(f"https://raw.githubusercontent.com/{repo}/HEAD/package.json", pick("name", "private", "repository"))
    if not r or r["status"] != 200:
        return None, None, "no package.json at the repository root" if r and r["status"] == 404 else why(r, "GitHub (root package.json)")
    pj = r["body"] or {}
    if pj.get("private") or not isinstance(pj.get("name"), str):
        return None, None, "the root package.json is not published (marked private, or unnamed)"
    n = npm_latest(src, pj["name"])
    if not n or n["status"] != 200:
        return None, None, f"the root package.json names {pj['name']}, and " + why(n, "npm's registry")
    back = gh_repo((n["body"] or {}).get("repository"))
    if back != repo.lower():
        return None, None, f"npm's {pj['name']} points to {back or 'no GitHub repository'}, not this one"
    return [f"npm:{pj['name']}"], "the root package.json names it, and npm's record points back to this repository", None

# ------------------------------------------------------------------ OSV and provenance, pinned to the version

def affected(record, system, name):
    norm = lambda s: re.sub(r"[-_.]+", "-", s).lower() if system == "pypi" else s
    out = []
    for a in record.get("affected") or []:
        p = a.get("package") or {}
        if p.get("ecosystem") != ECOSYSTEM[system] or norm(p.get("name") or "") != norm(name):
            continue
        for rg in a.get("ranges") or []:
            if rg.get("type") == "GIT":
                continue
            ev = {k: v for e in rg.get("events") or [] for k, v in e.items()}
            lo = "all versions" if ev.get("introduced") in ("0", None) else f">= {ev['introduced']}"
            out.append(lo + (f", < {ev['fixed']}" if "fixed" in ev else f", <= {ev['last_affected']}" if "last_affected" in ev else ""))
        if not a.get("ranges") and a.get("versions"):
            out.append("versions " + ", ".join(a["versions"]))
    return out

def advisory(src, vid, modified, system, name):
    source, licence = SOURCES.get(vid.split("-")[0], (None, None))
    row = {"id": vid, "link": f"https://osv.dev/vulnerability/{vid}", "source": source, "licence": licence, "modified": (modified or "")[:10] or None}
    if not source:
        return row | {"details": "not stored: this record's source licence is not one AirStack has cleared; follow the link"}
    r = src(f"{OSV}vulns/{vid}", osv_record)
    if not r or r["status"] != 200:
        return row | {"details": f"not read: {why(r, 'OSV')}"}
    b = r["body"]
    sev = b.get("database_severity") or next((f"{s.get('type')} {s.get('score')}" for s in b.get("severity") or []), None)
    return row | {"severity": sev, "affected": affected(b, system, name), "published": (b.get("published") or "")[:10] or None,
                  "aliases": sorted(b.get("aliases") or []), "withdrawn": (b.get("withdrawn") or "")[:10] or None}

def provenance(src, system, name, ver, robots, day):
    base = {"version": ver, "checked": day}
    if system == "pypi":
        return base | {"state": "not checked", "says": "Not checked: pypi.org's robots.txt closes its attestation API (/integrity/) to automated readers."
                       if robots.get("pypi-integrity") is False else "Not checked: PyPI's attestation API was not read in this run."}
    url = f"{NPM}-/npm/v1/attestations/{urllib.parse.quote(name, safe='@')}@{ver}"
    r = src(url, lambda b: [a.get("predicateType") for a in b.get("attestations") or []])
    if r and r["status"] == 200 and r["body"]:
        kinds = sorted(PREDICATES.get(p, p) for p in r["body"])
        return base | {"state": "attested", "types": kinds, "link": url,
                       "says": f"npm holds {', '.join(kinds)} for {name}@{ver} (read {day}); AirStack did not re-verify the signature."}
    if r and r["status"] == 404:
        return base | {"state": "absent", "says": f"npm holds no attestation for {name}@{ver} (read {day}). Most packages publish without one."}
    return base | {"state": "not checked", "says": f"Not checked: {why(r, 'npm attestations')}."}

def issues(recs):
    """How many distinct issues the records describe: a GHSA- and a PYSEC- record that alias each other are one."""
    groups = []
    for a in recs:
        ids = {a["id"], *(a.get("aliases") or [])}
        for g in [g for g in groups if g & ids]:
            groups.remove(g); ids |= g
        groups.append(ids)
    return len(groups)

def says(status, pkg, recs, day, reason=None):
    ids, n = ", ".join(a["id"] for a in recs), issues(recs)
    return {"reported": f"Reported in OSV for {pkg}: {ids}. Follow each link; read {day}.",
            "advisories": f"OSV lists {n} advisor{'y' if n == 1 else 'ies'} for {pkg}" + (f" ({len(recs)} records)" if len(recs) != n else "") + f": {ids}. Read {day}.",
            "none found": f"No matching advisories found on {day} for {pkg}. That is not a clean bill: OSV knows only what is reported to it.",
            "not checked": f"Not checked: {reason}."}[status]

def collect(src, universe, oss, robots, day):
    tools = {t["id"]: [f"npm:{p}" for p in t.get("npm") or []] + [f"pypi:{p}" for p in t.get("pypi") or []] for t in universe}
    declared = {t["github"].lower(): tools[t["id"]] for t in universe if t.get("github") and tools[t["id"]]}
    repos = {}
    for repo in sorted({r["repo"] for rows in oss["categories"].values() for r in rows}):
        pk, how, reason = repo_packages(src, repo, declared)
        repos[repo] = {"packages": pk, "how": how, "reason": reason}
    keys = sorted({k for v in tools.values() for k in v} | {k for r in repos.values() for k in r["packages"] or []})
    pkgs = {}
    for k in keys:
        system, name = k.split(":", 1)
        ver, published, how, reason = version(src, system, name)
        pkgs[k] = {"system": system, "name": name, "version": ver, "version_from": how, "released": published, "reason": reason}
    asked = [k for k in keys if pkgs[k]["version"]]
    queries = [{"package": {"ecosystem": ECOSYSTEM[pkgs[k]["system"]], "name": pkgs[k]["name"]}, "version": pkgs[k]["version"]} for k in asked]
    for i in range(0, len(queries), 1000):
        src(f"{OSV}querybatch", data=json.dumps({"queries": queries[i:i + 1000]}, sort_keys=True))
    answers = osv_answers(src.saved)                                       # pinned: package and version together
    for k in keys:
        p = pkgs[k]; pin = f"{p['name']}@{p['version']}"
        res, r = answers.get((ECOSYSTEM[p["system"]], p["name"], p["version"]), (None, None))
        if not p["version"]:
            p.update(status="not checked", advisories=None, reported=None, issues=None, partial=None, says=says("not checked", pin, [], day, p["reason"]))
        elif res is None:
            p.update(status="not checked", advisories=None, reported=None, issues=None, partial=None,
                     says=says("not checked", pin, [], day, f"OSV was not asked about {pin} in this run" if r is None else why(r, "OSV") + f" for {pin}"))
        else:
            recs = sorted((advisory(src, v["id"], v.get("modified"), p["system"], p["name"]) for v in res.get("vulns") or []), key=lambda a: a["id"])
            live_recs = [a for a in recs if not a.get("withdrawn")]
            reported = [a["id"] for a in live_recs if a["id"].startswith("MAL-")]
            status = "reported" if reported else "advisories" if live_recs else "none found"
            p.update(status=status, advisories=recs, reported=reported, issues=issues(live_recs), partial=bool(res.get("next_page_token")),
                     says=says(status, pin, [a for a in live_recs if a["id"] in reported] if reported else live_recs, day))
        answered = p["status"] != "not checked"
        p.update(checked=day if answered else None, covers=pin if answered else None,                 # what OSV's answer covers, and nothing later
                 registry=(f"https://www.npmjs.com/package/{p['name']}/v/{p['version']}" if p["system"] == "npm" else f"https://pypi.org/project/{p['name']}/{p['version']}/")
                 if p["version"] else None,
                 provenance=provenance(src, p["system"], p["name"], p["version"], robots, day) if p["version"] else None)
        p.pop("reason")
    return {"packages": pkgs, "tools": {t: v for t, v in sorted(tools.items()) if v}, "repos": repos}

def fetch_run():
    """Ask every source once and save the whole run (the questions too: the tracked tools and candidates it was asked about)."""
    universe = [pick("id", "npm", "pypi", "github")(t) for t in json.loads(paths.UNIVERSE.read_text())]
    oss = json.loads(paths.OSS.read_text())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds"); saved = {}
    robots = {n: fetch.allowed(u) for n, u in CLOSED.items()}
    collect(live(saved), universe, oss, robots, now[:10])
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{now[:10]}.json.gz").write_bytes(gzip.compress(json.dumps(
        {"fetched_at": now, "robots": robots, "kept": KEPT, "universe": universe, "oss_repos": sorted({r["repo"] for rows in oss["categories"].values() for r in rows}),
         "responses": saved}, ensure_ascii=False, sort_keys=True).encode(), mtime=0))

def build(raw_file=None, out=OUT):
    raw_file = raw_file or max(RAW.glob("*.json.gz"))
    run = json.loads(gzip.decompress(pathlib.Path(raw_file).read_bytes())); day = run["fetched_at"][:10]
    oss = {"categories": {"all": [{"repo": r} for r in run["oss_repos"]]}}
    d = collect(replay(run["responses"]), run["universe"], oss, run["robots"], day)
    closed = [n for n, ok in sorted(run["robots"].items()) if ok is False]
    d["source"] = {
        "read": run["fetched_at"], "raw": f"data/trust-raw/{pathlib.Path(raw_file).name}",
        "advisories": {"name": "OSV.dev", "url": "https://osv.dev", "api": OSV + "querybatch", "licence": "per record, by its source",
                       "sources": {p: {"name": n, "licence": l} for p, (n, l) in sorted(SOURCES.items())}},
        "versions": {"npm": {"name": "npm public registry (dist-tag latest)", "url": NPM, "terms": "https://docs.npmjs.com/policies/open-source-terms"},
                     "pypi": {"name": "PyPI release feeds (RSS)", "url": "https://pypi.org/rss/", "terms": "https://policies.python.org/pypi.org/Terms-of-Use/"}},
        "packages_from": {"tools": "data/universe.json", "repos": "each candidate's root package.json (raw.githubusercontent.com), kept only when npm's record points back"},
        "closed": {n: CLOSED[n] for n in closed},
        "note": "Each check names the version it covered (covers); a later release is not covered. Reported comes only from an OSV MAL- record, "
                "linked. No matching advisories found means OSV had no record for that version on that date, not that nothing is wrong. "
                "Provenance is npm's record of an attestation, not re-verified here; PyPI's is not checked while its robots.txt closes /integrity/. "
                "deps.dev is not read while its robots.txt closes its API, so a candidate's Python packages are not resolved. Nothing here runs a project's code."}
    pathlib.Path(out).write_text(json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    n = d["packages"].values()
    print(f"trust.json: {len(d['packages'])} packages ({sum(p['status'] == 'reported' for p in n)} reported, {sum(p['status'] == 'advisories' for p in n)} with advisories, "
          f"{sum(p['status'] == 'not checked' for p in n)} not checked), {sum(bool(r['packages']) for r in d['repos'].values())} of {len(d['repos'])} repositories resolved (read {day})")

if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--fetch", action="store_true"); args = a.parse_args()
    if args.fetch:
        fetch_run()
    build()
