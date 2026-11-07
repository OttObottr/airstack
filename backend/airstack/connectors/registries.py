# spec: AS-236 AS-289 AS-326
"""Keyless public registry signals: npm downloads, PyPI downloads (pypistats), Hacker News story counts (Algolia), GitHub repo facts.
Deterministic, no model. Every fetch goes through an injectable fetcher that returns an ENVELOPE:
    {"url", "fetched_at", "status", "body", "error"}      (body is parsed JSON or None; error is a reason string or None)
so tests never touch the network and a saved envelope replays a run exactly. Every result carries the url it came from and its
fetched_at. A signal that is unavailable is {"value": None, "reason": "..."}: never an estimate, never 0 for missing."""
import calendar, json, re, statistics, subprocess, time, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone

from airstack.fetch import UA                                          # one honest name (AS-274); registry APIs, not pages
NPM_RANGE = "https://api.npmjs.org/downloads/range/{span}/{pkg}"     # span: "last-month" or "<start>:<end>" (fixed dates replay exactly)
PYPI_OVERALL = "https://pypistats.org/api/packages/{pkg}/overall?mirrors=false"
HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"
GITHUB_API = "https://api.github.com/"
# gh output is projected to the fields used below (release notes and asset lists are large and not used); the envelope records the filter.
GH_REPO_JQ = "{full_name, stargazers_count, pushed_at, archived, html_url}"
GH_RELEASES_JQ = "[.[] | {tag_name, name, draft, prerelease, published_at, created_at, html_url}]"
RELEASES_PER_PAGE = 20

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _day(d):
    return d if isinstance(d, date) else date.fromisoformat(d)

def _missing(reason, env=None):
    out = {"value": None, "reason": reason}
    if env:
        out.update(url=env["url"], fetched_at=env["fetched_at"])
    return out

def _failed(env):
    return env.get("error") or (None if env.get("body") is not None else "empty response")

# ---------------------------------------------------------------- network fetchers (the only code that touches the network)

def http_fetch(url, *, timeout=20, sleep=time.sleep, now=utc_now):
    """GET a JSON URL. One retry: after Retry-After (capped) on HTTP 429, after 3 s on any other failure. Never raises."""
    err = status = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
                return {"url": url, "fetched_at": now(), "status": r.status, "body": json.loads(r.read().decode("utf-8")), "error": None}
        except urllib.error.HTTPError as e:
            status, err = e.code, f"HTTP {e.code}"
            if e.code == 404:
                break
            wait = 3
            if e.code == 429:
                err = "rate-limited (HTTP 429) after one retry"
                try:
                    wait = min(int(e.headers.get("Retry-After") or 15), 60)
                except ValueError:
                    wait = 15
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            status, err, wait = None, f"fetch failed: {type(e).__name__}", 3
        if attempt == 0:
            sleep(wait)
    return {"url": url, "fetched_at": now(), "status": status, "body": None, "error": err}

def gh_run(path, jq, *, sleep=time.sleep, now=utc_now):
    """`gh api <path> --jq <jq>` (the gh CLI's own auth; no key handled here). One retry. Never raises."""
    cmd = ["gh", "api", path, "--jq", jq]
    err = None
    for attempt in range(2):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if p.returncode == 0:
                return {"url": GITHUB_API + path, "fetched_at": now(), "status": 200, "body": json.loads(p.stdout), "error": None, "command": cmd}
            err = (p.stderr.strip().splitlines() or ["gh api failed"])[0][:200]
            if "Not Found" in err:
                break
        except (subprocess.TimeoutExpired, OSError, ValueError) as e:
            err = f"gh api failed: {type(e).__name__}"
        if attempt == 0:
            sleep(3)
    return {"url": GITHUB_API + path, "fetched_at": now(), "status": None, "body": None, "error": err, "command": cmd}

# ---------------------------------------------------------------- pure parsing + math

def week_delta(daily_rows, end_date, *, zero_is_gap=False):
    """daily_rows: [{"day": "YYYY-MM-DD", "downloads": int}]. last7 = the 7 days ending end_date, prior7 = the 7 days before.
    Each week needs all 7 days (nothing is interpolated): a bad last week nulls the value, a bad prior week nulls only the comparison.
    delta_pct = (last-prior)/prior*100 to 1 dp; None when prior is 0.
    zero_is_gap: a source that writes 0 for a day it has no data for (npm does, registry-wide) gets null rather than a fake total."""
    end = _day(end_date)
    days = [(end - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]          # oldest first
    by_day = {r["day"]: r["downloads"] for r in daily_rows}
    def problem(span):
        absent = [d for d in span if d not in by_day]
        if absent:
            return f"incomplete daily data: no row for {', '.join(absent)}"
        zeros = [d for d in span if zero_is_gap and by_day[d] == 0]
        return f"source reported 0 downloads on {', '.join(zeros)}, a reporting gap" if zeros else None
    if problem(days[7:]):
        return {"value": None, "reason": f"{problem(days[7:])}; no 7-day total computed"}
    last = sum(by_day[d] for d in days[7:])
    if problem(days[:7]):
        return {"value": last, "prior": None, "delta_pct": None, "delta_reason": f"prior 7 days unusable: {problem(days[:7])}"}
    prior = sum(by_day[d] for d in days[:7])
    out = {"value": last, "prior": prior, "delta_pct": round((last - prior) / prior * 100, 1) if prior else None}
    if not prior:
        out["delta_reason"] = "prior 7 days were 0; percent change undefined"
    # The tool's own recent level: the median of up to four FULL weeks before the compared week (needs two). One odd week (a dip or a spike from CI
    # and Docker pulls) can make a rebound look like growth; this says whether the last week is above what the tool usually does.
    earlier = []
    for i in range(2, 6):
        span = [(end - timedelta(days=7 * i + k)).isoformat() for k in range(7)]
        if all(d in by_day for d in span) and not (zero_is_gap and any(by_day[d] == 0 for d in span)):
            earlier.append(sum(by_day[d] for d in span))
    if len(earlier) >= 2:
        base = statistics.median(earlier)
        out.update({"base": base, "base_weeks": len(earlier), "vs_base_pct": round((last - base) / base * 100, 1) if base else None})
    return out

def week_series(daily_rows, end_date, weeks=26, *, zero_is_gap=False):
    """The `weeks` ISO weeks (Monday starts) ending with the week that holds end_date, oldest first: {"week", "downloads", "days", "partial"}.
    downloads sums the days observed on or before end_date (nothing is interpolated); days counts them; partial = fewer than 7.
    A week with no observed day is null, never 0. zero_is_gap as in week_delta: a source that writes 0 for missing days."""
    end = _day(end_date)
    by_day = {r["day"]: r["downloads"] for r in daily_rows if not (zero_is_gap and r["downloads"] == 0)}
    first = end - timedelta(days=end.weekday() + 7 * (weeks - 1))
    out = []
    for w in range(weeks):
        span = [first + timedelta(days=7 * w + k) for k in range(7)]
        seen = [by_day[d.isoformat()] for d in span if d <= end and d.isoformat() in by_day]
        out.append({"week": span[0].isoformat(), "downloads": sum(seen) if seen else None, "days": len(seen), "partial": len(seen) < 7})
    return out

def weeks_span(end_date, weeks=26):
    """npm's range span for week_series: the first week's Monday to end_date."""
    end = _day(end_date)
    return f"{(end - timedelta(days=end.weekday() + 7 * (weeks - 1))).isoformat()}:{end.isoformat()}"

# A shell install command in a README: pip/uv/poetry/pipx install PyPI packages; npm/pnpm/yarn/bun/npx install or run npm packages.
INSTALL = re.compile(r"\b(?:(?P<pypi>(?:uv\s+)?pip3?\s+install|uv\s+add|uv\s+tool\s+install|poetry\s+add|pipx\s+install)"
                     r"|(?P<npm>npm\s+(?:install|i|add)|pnpm\s+(?:add|dlx)|yarn\s+(?:global\s+)?add|bun\s+add|bunx|npx))\s+[^\n`|;&#<]+")

def install_lines(text):
    """Every install command in a README, in document order, each cut to one line of at most 200 characters."""
    return [m.group(0).strip()[:200] for m in INSTALL.finditer(text or "")]

def pypi_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()                            # PEP 503: lm_eval and lm-eval are one package

def installed(line):
    """(registry, [package names]) an install line names, in order; flags, extras, versions and local paths dropped."""
    m = INSTALL.match(line)
    if not m:
        return None, []
    registry, names = ("pypi" if m.group("pypi") else "npm"), []
    runs = re.fullmatch(r"npx|bunx|pnpm\s+dlx", m.group("npm") or "")    # runs ONE package; the words after it are its arguments
    for tok in line[m.end(registry):].split():
        if runs and names:
            break
        tok = tok.strip("'\"")
        if not tok or tok.startswith(("-", ".", "/", "git+", "http")) or "://" in tok:
            continue
        if registry == "pypi":
            name = re.split(r"[\[<>=!~@;,]", tok)[0]
            ok = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name)
            name = pypi_name(name)
        else:
            name = "@" + tok[1:].split("@")[0] if tok.startswith("@") else tok.split("@")[0]
            ok = re.fullmatch(r"(@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*", name)
        if ok:
            names.append(name)
    return registry, names

def fetch_npm_range(pkg, fetch, span="last-month"):
    """npm daily downloads for the last month (or a fixed "<start>:<end>" span). -> {"package","url","fetched_at","end","rows"} or a null with reason."""
    env = fetch(NPM_RANGE.format(span=span, pkg=pkg))
    if _failed(env):
        return {"package": pkg, **_missing(f"npm downloads API: {_failed(env)}", env)}
    b = env["body"]
    if "downloads" not in b:
        return {"package": pkg, **_missing(f"npm downloads API: {b.get('error', 'no downloads field')}", env)}
    return {"package": pkg, "url": env["url"], "fetched_at": env["fetched_at"], "end": b.get("end"),
            "rows": [{"day": r["day"], "downloads": r["downloads"]} for r in b["downloads"]]}

def fetch_pypi_overall(pkg, fetch):
    """pypistats daily downloads without mirrors. -> {"package","url","fetched_at","end","rows"} or a null with reason."""
    env = fetch(PYPI_OVERALL.format(pkg=pkg))
    if _failed(env):
        return {"package": pkg, **_missing(f"pypistats API: {_failed(env)}", env)}
    rows = sorted(({"day": r["date"], "downloads": r["downloads"]} for r in env["body"].get("data", []) if r.get("category") == "without_mirrors"),
                  key=lambda r: r["day"])
    if not rows:
        return {"package": pkg, **_missing("pypistats API: no without_mirrors rows", env)}
    return {"package": pkg, "url": env["url"], "fetched_at": env["fetched_at"], "end": rows[-1]["day"], "rows": rows}

def make_window(end_date):
    end = _day(end_date)
    f = lambda n: (end - timedelta(days=n)).isoformat()
    return {"last7": [f(6), f(0)], "prior7": [f(13), f(7)]}

def hn_url(query, start, end):
    """Stories created on [start, end] (UTC days, inclusive). typoTolerance/prefixNone make it count the name itself, not near-misses."""
    lo = calendar.timegm(_day(start).timetuple()) - 1
    hi = calendar.timegm((_day(end) + timedelta(days=1)).timetuple())
    return HN_SEARCH + "?" + urllib.parse.urlencode({"query": query, "tags": "story", "numericFilters": f"created_at_i>{lo},created_at_i<{hi}",
                                                     "hitsPerPage": 0, "typoTolerance": "false", "queryType": "prefixNone"})

def hn_counts(query, window, fetch):
    """Hacker News story counts (Algolia nbHits) for window["last7"] vs window["prior7"]. delta = last - prior (a count difference)."""
    cur, pri = fetch(hn_url(query, *window["last7"])), fetch(hn_url(query, *window["prior7"]))
    for env in (cur, pri):
        if _failed(env) or "nbHits" not in env["body"]:
            return {"query": query, **_missing(f"HN Algolia API: {_failed(env) or 'no nbHits field'}", env)}
    v, p = cur["body"]["nbHits"], pri["body"]["nbHits"]
    return {"value": v, "prior": p, "delta": v - p, "query": query, "url": cur["url"], "fetched_at": cur["fetched_at"],
            "prior_url": pri["url"], "prior_fetched_at": pri["fetched_at"],
            "exhaustive": bool(cur["body"].get("exhaustiveNbHits")) and bool(pri["body"].get("exhaustiveNbHits"))}

def _ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def _names_package(tag, packages):
    return any(tag.startswith(p + sep) for p in packages for sep in ("@", "==", "-v"))

def github_repo(repo, run, packages=()):
    """Current stars (no delta: there is no prior snapshot), pushed_at, latest stable release, releases in the 30 days before the fetch.
    In a monorepo (tags like "ai@7.0.1", "langchain==1.4.8") the latest release is the newest one tagged with one of `packages`."""
    env = run(f"repos/{repo}", GH_REPO_JQ)
    if _failed(env):
        return _missing(f"GitHub API: {_failed(env)}", env)
    rel = run(f"repos/{repo}/releases?per_page={RELEASES_PER_PAGE}", GH_RELEASES_JQ)
    b = env["body"]
    out = {"repo": b.get("full_name") or repo, "stars": b["stargazers_count"], "pushed_at": b.get("pushed_at"), "archived": bool(b.get("archived")),
           "url": env["url"], "fetched_at": env["fetched_at"], "releases_url": rel["url"], "releases_fetched_at": rel["fetched_at"]}
    if _failed(rel):
        return {**out, "last_release": None, "last_release_at": None, "releases_30d": None,
                "releases_reason": f"GitHub releases API: {_failed(rel)}"}
    published = sorted((r for r in rel["body"] if not r.get("draft") and r.get("published_at")), key=lambda r: r["published_at"], reverse=True)
    stable = [r for r in published if not r.get("prerelease")]
    stable = [r for r in stable if _names_package(r["tag_name"], packages)] or stable
    cutoff = _ts(rel["fetched_at"]) - timedelta(days=30)
    recent = [r for r in published if _ts(r["published_at"]) > cutoff]
    out.update(last_release=stable[0]["tag_name"] if stable else None, last_release_at=stable[0]["published_at"] if stable else None,
               releases_30d=len(recent), releases_30d_capped=len(rel["body"]) >= RELEASES_PER_PAGE and len(recent) == len(published))
    if not stable:
        out["last_release_reason"] = ("no GitHub releases published" if not published else
                                      f"no stable release among the {len(published)} most recent (all prereleases)")
    return out
