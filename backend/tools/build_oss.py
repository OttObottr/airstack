# spec: AS-251 AS-295
"""Open-source alternatives per business category, from GitHub's own search API: the most-starred, non-archived repositories on the
category's topics, each with its stars, licence and last push. Every raw response is saved with its query and time (data/github-raw/),
and the build repeats offline. No model call, no cost.

One optional build-only pass queries Hacker News for exact repository links. It saves one response per unique repository and publishes only
actual linked discussions; a missing snapshot or failed refresh never becomes a measured zero. No unavailable social source is rendered.

Each candidate is vetted with OpenSSF Scorecard's public API (automated security checks: dangerous CI workflows, committed binaries,
maintenance, code review, known vulnerabilities). Projects that pass rank first; the rest are listed with what the checks found. The
checks are automated, not an audit, and the page says so.

Usage:  ../.venv/bin/python tools/build_oss.py --fetch     # query GitHub (uses the gh CLI's own login), save every response
        ../.venv/bin/python tools/build_oss.py --vet       # fetch each candidate's OpenSSF Scorecard, save every response
        ../.venv/bin/python tools/build_oss.py --social    # fetch exact repository-linked Hacker News stories, bounded and free
        ../.venv/bin/python tools/build_oss.py             # rebuild oss.json offline from the saved responses"""
import argparse, gzip, json, subprocess, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from airstack import paths
from airstack.fetch import UA

ROOT = paths.ROOT
RAW, OUT, VET, SOCIAL = paths.DATA / "github-raw", paths.OSS, paths.DATA / "scorecard-raw", paths.DATA / "oss-social-raw"
SCORECARD = "https://api.securityscorecards.dev/projects/github.com/"
HN_SEARCH, SOCIAL_DAYS = "https://hn.algolia.com/api/v1/search_by_date", 30
MIN_STARS = 500
import re
LISTS = re.compile(r"awesome|\b(list|collection) of\b|curated|interview|hiring|roadmap|cheat ?sheet|resources", re.I)
TOPICS = {   # category -> GitHub topics whose projects do the same job (a lead, labelled as such on the page)
    "creative-ai": ["text-to-video", "video-generation", "image-generation", "text-to-speech"],
    "ai-assistants": ["chatgpt-alternative", "llm-ui", "chat-ui"],
    "ai-coding": ["coding-agent", "ai-coding-assistant", "code-assistant"],
    "docs-storage": ["notion-alternative", "knowledge-base", "file-sharing"],
    "project-management": ["project-management", "kanban", "jira-alternative"],
    "chat-meetings": ["slack-alternative", "team-chat", "video-conferencing"],
    "crm-sales": ["crm", "salesforce-alternative"],
    "support": ["helpdesk", "customer-support", "zendesk-alternative"],
    "design": ["figma-alternative", "design-tool", "whiteboard"],
    "email-calendar": ["calendly-alternative", "email-client", "calendar"],
    "data-bi": ["business-intelligence", "data-visualization", "analytics"],
    "marketing": ["email-marketing", "marketing-automation", "newsletter"],
    "finance": ["accounting", "invoicing", "personal-finance"],
    "hr-people": ["hrms", "human-resources", "applicant-tracking-system"],
    "security-it": ["password-manager", "siem", "identity-management"],
    "dev-platforms": ["paas", "heroku-alternative", "self-hosted"],
    "web-commerce": ["ecommerce", "headless-commerce", "shopify-alternative"],
    "forms-surveys": ["form-builder", "survey", "typeform-alternative"],
    "legal-contracts": ["docusign-alternative", "e-signature", "digital-signature"],
    "video-webinars": ["video-conferencing", "live-streaming", "webinar"],
    "learning": ["lms", "learning-management-system", "e-learning"],
    "it-service": ["itsm", "asset-management", "service-desk"],
    "spend-procurement": ["procurement", "expense-management", "erp"],
}

def fetch():
    RAW.mkdir(parents=True, exist_ok=True)
    for cat, topics in TOPICS.items():
        for t in topics:
            f = RAW / f"{cat}--{t}.json.gz"
            if f.exists():
                continue
            q = f"topic:{t} stars:>={MIN_STARS} archived:false"
            out = subprocess.run(["gh", "api", "-X", "GET", "search/repositories", "-f", f"q={q}", "-f", "sort=stars", "-f", "per_page=20"],
                                 capture_output=True, text=True)
            if out.returncode:
                print("failed", cat, t, out.stderr[:120]); time.sleep(10); continue
            body = json.loads(out.stdout)
            f.write_bytes(gzip.compress(json.dumps({"endpoint": "https://api.github.com/search/repositories", "query": q, "sort": "stars",
                                                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "items": body.get("items", [])},
                                                   ensure_ascii=False, sort_keys=True).encode(), mtime=0))
            time.sleep(2.2)                                                # under GitHub's 30 searches a minute

def candidates():
    """Every repository a category could list: the search results that are projects (not archived, not forks, not link lists)."""
    out = {}
    for f in sorted(RAW.glob("*.json.gz")):
        d = json.loads(gzip.decompress(f.read_bytes())); cat = f.name.split("--")[0]
        for r in d["items"]:
            if r.get("archived") or r.get("fork") or not r.get("description") or LISTS.search(r["full_name"] + " " + r["description"]):
                continue                                                   # a project, not a curated list of links
            out.setdefault(cat, {})[r["full_name"]] = r
    return out

def vet_file(repo):
    return VET / (repo.replace("/", "__") + ".json.gz")

def social_file(repo):
    return SOCIAL / (repo.replace("/", "__") + ".json.gz")

def fetch_social():
    """One bounded HN search per unique repository. A failed refresh never replaces the last successful snapshot."""
    SOCIAL.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    since = int((now - timedelta(days=SOCIAL_DAYS)).timestamp())
    repos = sorted({repo for rows in candidates().values() for repo in rows})
    def read(repo):
        old = social_file(repo)
        if old.exists():
            saved = json.loads(gzip.decompress(old.read_bytes()))
            if (now - datetime.fromisoformat(saved["fetched_at"])).days < 7:
                return repo, None
        query = f"github.com/{repo}"
        params = urllib.parse.urlencode({"query": query, "tags": "story", "restrictSearchableAttributes": "url",
                                         "numericFilters": f"created_at_i>{since}", "hitsPerPage": 100})
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{HN_SEARCH}?{params}", headers={"User-Agent": UA, "Accept": "application/json"}), timeout=20) as response:
                body = json.loads(response.read(2_000_000))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            return repo, str(error)
        snapshot = {"source": HN_SEARCH, "query": query, "window": [(now - timedelta(days=SOCIAL_DAYS)).date().isoformat(), now.date().isoformat()],
                    "fetched_at": now.isoformat(timespec="seconds"), "response": body}
        old.write_bytes(gzip.compress(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode(), mtime=0))
        return repo, None
    with ThreadPoolExecutor(max_workers=2) as pool:
        failed = [repo for repo, error in pool.map(read, repos) if error]
    print(f"oss social: {len(repos) - len(failed)} snapshots ready, {len(failed)} refreshes failed")

def discussion(repo):
    """Exact repository-linked HN stories from the saved search; missing input is not a measured zero."""
    file = social_file(repo)
    if not file.exists():
        return {"status": "not_indexed"}
    data = json.loads(gzip.decompress(file.read_bytes()))
    want = f"github.com/{repo}".lower()
    hits = []
    for hit in data["response"].get("hits", []):
        target = (hit.get("url") or "").lower().split("?", 1)[0].rstrip("/")
        if target == f"https://{want}" or target.startswith(f"https://{want}/"):
            hits.append({"title": hit.get("title") or repo, "url": hit["url"], "discussion": f"https://news.ycombinator.com/item?id={hit['objectID']}",
                         "date": (hit.get("created_at") or "")[:10], "points": hit.get("points") or 0, "comments": hit.get("num_comments") or 0})
    hits.sort(key=lambda h: (h["date"], h["points"], h["comments"]), reverse=True)
    return {"status": "observed" if hits else "not_observed", "source": data["source"], "query": data["query"], "window": data["window"],
            "fetched_at": data["fetched_at"], "count": len(hits), "items": hits[:3], "truncated": len(hits) > 3}

def vet():
    """Save each candidate's OpenSSF Scorecard result (or the API's answer that it has none). Public API, no key."""
    VET.mkdir(parents=True, exist_ok=True)
    repos = sorted({r for c in candidates().values() for r in c})
    for repo in repos:
        f = vet_file(repo)
        if f.exists():
            continue
        req = urllib.request.Request(SCORECARD + repo, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                status, body = r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            status, body = e.code, None
        except (urllib.error.URLError, TimeoutError) as e:
            print("skipped", repo, e); continue                           # not saved: a later run tries again
        f.write_bytes(gzip.compress(json.dumps({"endpoint": SCORECARD + repo, "status": status, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                "result": body}, ensure_ascii=False, sort_keys=True).encode(), mtime=0))
        time.sleep(0.25)
    print(f"scorecard: {len(repos)} repositories, {sum(1 for _ in VET.glob('*.json.gz'))} saved")

ORDER = [("Maintained", "Maintained"), ("Code-Review", "Code review"), ("Dangerous-Workflow", "Safe CI workflows"), ("Binary-Artifacts", "No committed binaries"),
         ("Vulnerabilities", "No known vulnerabilities (OSV)"), ("Security-Policy", "Security policy"), ("Signed-Releases", "Signed releases"),
         ("Branch-Protection", "Branch protection"), ("Token-Permissions", "Least-privilege CI tokens"), ("Pinned-Dependencies", "Pinned dependencies")]
HARD = {"Dangerous-Workflow": (lambda s: s == 0, "dangerous CI workflow"), "Binary-Artifacts": (lambda s: 0 <= s < 8, "binary files committed"),
        "Vulnerabilities": (lambda s: 0 <= s < 7, "known vulnerabilities open (OSV)")}
SOFT = {"Maintained": (lambda s: s == 0, "no activity in 90 days")}

def checks(repo, created, fetched):
    """What the automated checks say, in plain words; a missing or low score is said, never hidden."""
    f = vet_file(repo)
    if not f.exists():
        return None, ["not checked yet"]
    d = json.loads(gzip.decompress(f.read_bytes())); res = d.get("result")
    flags = []
    if not res or res.get("score") is None:
        return None, ["not scanned by OpenSSF Scorecard (unknown, not a finding)"]
    by = {c["name"]: c.get("score", -1) for c in res.get("checks") or []}
    for name, (bad, say) in {**HARD, **SOFT}.items():
        if name in by and by[name] is not None and bad(by[name]): flags.append(say)
    if res["score"] < 4: flags.insert(0, f"low security score ({res['score']}/10)")
    if created and fetched and created[:4].isdigit() and (int(fetched[:4]) * 12 + int(fetched[5:7])) - (int(created[:4]) * 12 + int(created[5:7])) < 12:
        flags.append(f"under a year old (created {created[:10]}): check its history")
    sc = {"score": res["score"], "date": (res.get("date") or "")[:10], "url": "https://scorecard.dev/viewer/?uri=github.com/" + repo,
          "commit": ((res.get("repo") or {}).get("commit") or "")[:12] or None,                 # the exact commit the checks ran on: a new commit is not covered
          "checks": [by[k] if by.get(k) is not None and by[k] >= 0 else None for k, _ in ORDER]}      # the reputation graph: 0-10 per check, None = not applicable
    return sc, flags

def build():
    fetched = max(json.loads(gzip.decompress(f.read_bytes()))["fetched_at"] for f in RAW.glob("*.json.gz"))
    vetted_at = max((json.loads(gzip.decompress(f.read_bytes()))["fetched_at"] for f in VET.glob("*.json.gz")), default=None)
    cats = {}
    for cat, repos in candidates().items():
        for name, r in repos.items():
            sc, flags = checks(name, r.get("created_at"), fetched)
            lic = (r.get("license") or {}).get("spdx_id") or None
            stale = (r.get("pushed_at") or "")[:10] < (datetime.fromisoformat(fetched) - timedelta(days=180)).date().isoformat()
            gate = "no licence stated" if lic in (None, "NOASSERTION") else "no push in 180 days" if stale else None   # below the gate: listed, never offered as an alternative
            cats.setdefault(cat, {})[name] = {"repo": name, "url": r["html_url"], "description": r["description"][:160],
                                              "stars": r["stargazers_count"], "license": (r.get("license") or {}).get("spdx_id") or None,
                                              "forks": r.get("forks_count"), "open_issues_and_pull_requests": r.get("open_issues_count"),
                                              "discussions_enabled": bool(r.get("has_discussions")),
                                              "community": {"hacker_news": discussion(name)},
                                              "pushed": (r.get("pushed_at") or "")[:10], "created": (r.get("created_at") or "")[:10] or None,
                                              "homepage": r.get("homepage") or None, "scorecard": sc, "flags": flags,
                                              "gate": gate,
                                              "vetted": not gate and bool(sc) and sc["score"] >= 5 and not any(x in flags for _, x in HARD.values())}
    out = {"source": {"name": "GitHub search API", "url": "https://api.github.com/search/repositories", "fetched_at": fetched, "min_stars": MIN_STARS,
                      "checks": {"name": "OpenSSF Scorecard", "url": "https://scorecard.dev", "license": "CDLA-Permissive-2.0", "license_url": "https://cdla.dev/permissive-2-0/",
                                 "fetched_at": vetted_at, "order": [label for _, label in ORDER],
                                 "passes": "a score of 5 or more, no dangerous CI workflow, no committed binaries, no open known vulnerabilities"},
                      "note": "Candidates found through this category's GitHub topics. Stars and forks show repository attention, not use, trust or social sentiment. Projects that pass OpenSSF Scorecard's automated checks "
                              "(pinned to the commit checked) rank first, by score; the rest follow with what the checks found; projects with no licence or no push in 180 days "
                              "are listed apart, never as alternatives. Automated checks, not an audit: read the code and the licence before you run anything."},
           "categories": {c: sorted(v.values(), key=lambda r: (bool(r["gate"]), not r["vetted"], -(r["scorecard"] or {}).get("score", 0) if r["vetted"] else 0, -r["stars"]))[:12]
                          for c, v in sorted(cats.items())}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"oss.json: {sum(len(v) for v in out['categories'].values())} repositories in {len(out['categories'])} categories (read {fetched})")

if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--fetch", action="store_true"); a.add_argument("--vet", action="store_true"); a.add_argument("--social", action="store_true"); args = a.parse_args()
    if args.fetch:
        fetch()
    if args.vet:
        vet()
    if args.social:
        fetch_social()
    build()
