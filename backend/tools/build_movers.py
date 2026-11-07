# spec: AS-236 AS-289 AS-326
"""Builds data/movers.json: dated, keyless public signals for the tools in data/universe.json. Deterministic; no model, no key.
A run saves every response as {"url","fetched_at","status","body","error"} in ONE file, data/movers-raw/<date>.json.gz ({url: envelope}),
and movers.json is then built FROM THE NEWEST RUN FILE, so `--offline` (no network) reproduces it byte for byte.
The window ends on the latest day both npm and pypistats have published (npm's own `end`), so no source is asked for a day it lacks.
Each tool also gets 26 weeks of weekly downloads (AS-289) and, per registry, the package the page measures, its siblings and the
primary package by rule (AS-236). Web requests go through airstack.fetch (honest name, robots.txt, Retry-After); GitHub through `gh api`.
A run in which every request to one host failed is not saved: the previous run stays (an outage never blanks a source).
Usage: python backend/tools/build_movers.py [--offline]"""
import argparse, gzip, hashlib, json, pathlib, sys, time, urllib.parse
from datetime import date, datetime, timedelta, timezone
from airstack.connectors import registries as reg
from airstack.fetch import get
from airstack import paths

ROOT = paths.ROOT
UNIVERSE = paths.UNIVERSE
RAW = paths.DATA / "movers-raw"
OUT = paths.MOVERS
LANES = {"coding-agents": "Coding agents", "llm-sdks-and-routers": "LLM SDKs and routers", "vector-dbs": "Vector databases",
         "llm-observability": "LLM observability", "meeting-notes": "Meeting notes", "agent-frameworks": "Agent frameworks",
         "llm-evals": "LLM evals", "local-inference": "Local inference", "speech-ai": "Speech AI", "browser-agents": "Browser agents",
         "ai-app-builders": "AI app builders", "workflow-automation": "Workflow automation"}   # every universe lane, in display order
SAAS_LANES = {"meeting-notes", "ai-app-builders"}
SAAS_REASON = "SaaS app: no public package registry"
GENERIC_REASON = "name too generic to count reliably"
POLITE = {"pypistats.org": 1.0, "hn.algolia.com": 0.5, "api.npmjs.org": 1.0, "api.github.com": 0.3, "raw.githubusercontent.com": 0.5}   # seconds before each request
WEEKS = 26
BACKOFF = 30                                                               # seconds after a 429 that gave no Retry-After
README = "https://raw.githubusercontent.com/{repo}/HEAD/README.md"
README_CUT = "install commands only (pip, uv, poetry, pipx, npm, pnpm, yarn, bun, npx): the README itself is not stored"

def raw_path(url, raw_dir=RAW):
    """The per-URL file name of the older raw format (still used by corroborate.py for data/registry-raw/)."""
    return pathlib.Path(raw_dir) / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".json")

def dumps(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"

def envelope(url, now=reg.utc_now, sleep=time.sleep):
    """One GET through airstack.fetch, as an envelope. A README keeps only its install commands (the envelope says so).
    airstack.fetch waits out a 429's Retry-After; npm sends 429 without one, so that gets one retry after BACKOFF seconds."""
    for attempt in (0, 1):
        status, text, h = get(url, {"Accept": "application/json, text/plain;q=0.9"})
        if status != 429 or attempt:
            break
        sleep(BACKOFF)
    env = {"url": url, "fetched_at": now(), "status": status or None, "body": None, "error": None}
    if status != 200:
        env["error"] = (f"HTTP {status}" if status else "not fetched: robots.txt does not allow AirStackBot, or could not be read" if h.get("x-robots")
                        else "not fetched: the host's terms bar automated reading" if h.get("x-terms") else "no response")
    elif url.startswith(README.split("{")[0]):
        env.update(body={"install_lines": reg.install_lines(text)}, projection=README_CUT)
    else:
        try:
            env["body"] = json.loads(text)
        except ValueError:
            env["error"] = "response was not JSON"
    return env

def recording(sleep=time.sleep):
    """Online fetchers: polite, sequential; every envelope (failures included) is kept in `saved` for the run file."""
    saved = {}
    def fetch(url):
        sleep(POLITE.get(urllib.parse.urlsplit(url).hostname, 0.5))
        saved[url] = envelope(url, sleep=sleep)
        return saved[url]
    def run(path, jq):
        sleep(POLITE["api.github.com"])
        env = saved[reg.GITHUB_API + path] = reg.gh_run(path, jq, sleep=sleep)
        return env
    return fetch, run, saved

def save_run(saved, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(saved, sort_keys=True, ensure_ascii=False).encode("utf-8"), mtime=0))

def latest_run(raw_dir=RAW):
    runs = sorted(pathlib.Path(raw_dir).glob("*.json.gz"))
    if not runs:
        raise FileNotFoundError(f"no run file in {raw_dir}; run without --offline first")
    return runs[-1]

def dead_hosts(saved):
    """Hosts every request of this run failed for (an outage, or a host that closed itself to AirStackBot)."""
    errors = {}
    for env in saved.values():
        errors.setdefault(urllib.parse.urlsplit(env["url"]).hostname, []).append(reg._failed(env))
    return sorted(h for h, e in errors.items() if all(e))

class Raw:
    """Offline fetchers: replay saved envelopes from a run file (<date>.json.gz) or, for corroborate.py, a directory of per-URL files.
    A missing response is an error (an offline build never guesses)."""
    def __init__(self, src=RAW):
        src = pathlib.Path(src)
        self.saved = json.loads(gzip.decompress(src.read_bytes())) if src.is_file() else None
        self.dir, self.used = src, set()
    def fetch(self, url):
        if self.saved is not None:
            if url not in self.saved:
                raise FileNotFoundError(f"no saved response for {url} in {self.dir.name}; run without --offline first")
            self.used.add(url)
            return self.saved[url]
        p = raw_path(url, self.dir)
        if not p.exists():
            raise FileNotFoundError(f"no saved response for {url} ({p.name}); run without --offline first")
        self.used.add(p.name)
        return json.loads(p.read_text())
    def run(self, path, jq):
        return self.fetch(reg.GITHUB_API + path)

def _window_end(npm, pypi, stamps):
    ends = [max(r["end"] for r in rs if r.get("end")) for rs in (npm, pypi) if any(r.get("end") for r in rs)]
    if ends:
        return min(ends)
    if not stamps:
        raise ValueError("cannot anchor the window: the universe has no npm or PyPI package")
    return (date.fromisoformat(min(stamps)[:10]) - timedelta(days=1)).isoformat()   # every download fetch failed: the day before the run

def _downloads(results, registry, end, saas):
    if not results:
        return {"value": None, "reason": SAAS_REASON if saas else f"no {registry} package"}
    if len(results) > 1:
        raise ValueError("one package per registry per tool (summing packages is not defined)")
    r = results[0]
    if "rows" not in r:
        return {k: r[k] for k in ("value", "reason", "package", "url", "fetched_at") if k in r}
    return {**reg.week_delta(r["rows"], end, zero_is_gap=(registry == "npm")), "package": r["package"], "url": r["url"], "fetched_at": r["fetched_at"]}

def _cite(r):
    return {k: r[k] for k in ("package", "url", "fetched_at") if k in r}

def _weeks(r, end, registry):
    """AS-289: the tracked package's weekly series, from the same response its 7-day figures (PyPI) or its 26-week range (npm) came from."""
    if "rows" not in r:
        return {**_cite(r), "series": None, "reason": r["reason"]}
    return {**_cite(r), "series": reg.week_series(r["rows"], end, WEEKS, zero_is_gap=(registry == "npm"))}

def _primary(registry, candidates, readme):
    """AS-236: which package is the product. Rules, in order: the only package listed; the first install command in the tool's own
    README that names one of its packages; the most downloads in the last 7 days, only when every candidate was observed. Else null."""
    names = [c["package"] for c in candidates]
    if len(names) == 1:
        return {"primary": names[0], "rule": "only-package"}
    key = reg.pypi_name if registry == "pypi" else str
    if readme and not reg._failed(readme):
        for line in readme["body"]["install_lines"]:
            kind, named = reg.installed(line)
            hit = next((c for n in named for c in names if key(c) == n), None) if kind == registry else None
            if hit:
                return {"primary": hit, "rule": "readme-install-line",
                        "evidence": {"url": readme["url"], "fetched_at": readme["fetched_at"], "line": " ".join(line.split()[:25])}}
    unseen = [c["package"] for c in candidates if c.get("last7") is None]
    if unseen:
        why = "no install command in the README names one of them" if readme and not reg._failed(readme) else \
              f"README not read ({reg._failed(readme)})" if readme else "no GitHub repository to read a README from"
        return {"primary": None, "rule": None, "reason": f"{why}, and downloads were not observed for {', '.join(unseen)}"}
    return {"primary": max(candidates, key=lambda c: c["last7"])["package"], "rule": "highest-downloads"}

def _packages(t, npm_hist, pypi_hist, end, f):
    """Per registry: the package the page measures (tracked, from data/universe.json), the primary by rule, and every candidate's 7-day downloads."""
    siblings = t.get("siblings", {})
    readme = f(README.format(repo=t["github"])) if t["github"] and any(siblings.values()) else None
    out = {}
    for registry, hist in (("npm", npm_hist), ("pypi", pypi_hist)):
        if not t[registry]:
            continue
        candidates = []
        for r in hist:
            d = reg.week_delta(r["rows"], end, zero_is_gap=(registry == "npm")) if "rows" in r else {"value": None, "reason": r["reason"]}
            candidates.append({**_cite(r), "last7": d["value"], **({"reason": d["reason"]} if d["value"] is None else {})})
        out[registry] = {"tracked": t[registry][0], **_primary(registry, candidates, readme), "candidates": candidates if len(candidates) > 1 else []}
    return out

def build(universe, fetch, run):
    """The whole dataset from two fetchers. Pure given the fetchers: same envelopes in, same dict out."""
    unknown = sorted({t["lane"] for t in universe} - set(LANES))
    if unknown:
        raise ValueError(f"lane(s) not declared in LANES: {', '.join(unknown)}")
    for t in universe:
        for registry, sibs in t.get("siblings", {}).items():
            if not t[registry] or set(sibs) & set(t[registry]):
                raise ValueError(f"{t['id']}: siblings are other {registry} packages of a tool that has a tracked {registry} package")
    stamps = []
    def f(url):
        env = fetch(url); stamps.append(env["fetched_at"]); return env
    def g(path, jq):
        env = run(path, jq); stamps.append(env["fetched_at"]); return env
    npm = {t["id"]: [reg.fetch_npm_range(p, f) for p in t["npm"]] for t in universe}
    pypi = {t["id"]: [reg.fetch_pypi_overall(p, f) for p in t["pypi"]] for t in universe}
    end = _window_end([r for rs in npm.values() for r in rs], [r for rs in pypi.values() for r in rs], stamps)
    window = reg.make_window(end)
    span = reg.weeks_span(end, WEEKS)
    tools = []
    for t in universe:
        saas = t["lane"] in SAAS_LANES
        hn = reg.hn_counts(t["hn_query"], window, f) if t["hn_query"] else {"value": None, "reason": GENERIC_REASON}
        gh = reg.github_repo(t["github"], g, t["npm"] + t["pypi"]) if t["github"] else {"value": None, "reason": SAAS_REASON if saas else "no public GitHub repository"}
        # History and siblings come from their own responses and never feed the 7-day figures above.
        sib = t.get("siblings", {})
        npm_hist = [reg.fetch_npm_range(p, f, span) for p in t["npm"] + sib.get("npm", [])]
        pypi_hist = pypi[t["id"]] + [reg.fetch_pypi_overall(p, f) for p in sib.get("pypi", [])]
        tools.append({"id": t["id"], "name": t["name"], "lane": t["lane"], "homepage": t["homepage"], "signals": {
            "npm_7d": _downloads(npm[t["id"]], "npm", end, saas), "pypi_7d": _downloads(pypi[t["id"]], "PyPI", end, saas),
            "hn_7d": hn, "github": gh},
            "weeks": {k: _weeks(h[0], end, k) for k, h in (("npm", npm_hist), ("pypi", pypi_hist)) if t[k]},
            "packages": _packages(t, npm_hist, pypi_hist, end, f)})
    lanes = []
    for lane in dict.fromkeys(t["lane"] for t in tools):
        ts = [t for t in tools if t["lane"] == lane]
        lanes.append({"lane": lane, "tools": len(ts),
                      "with_downloads_delta": sum(any(t["signals"][k].get("delta_pct") is not None for k in ("npm_7d", "pypi_7d")) for t in ts),
                      "with_hn_counts": sum(t["signals"]["hn_7d"].get("value") is not None for t in ts)})
    return {"generated_at": max(stamps) if stamps else None, "window": window,
            "notes": {"downloads": "7-day sums of daily downloads; delta_pct = (last7 - prior7) / prior7 * 100, 1 dp; vs_base_pct = last7 against the median of up to four earlier full weeks (needs two), the tool's own recent level",
                      "hn": "Hacker News stories (Algolia nbHits, typo tolerance off) matching the exact query; delta = last7 - prior7",
                      "github": "stars are the current count only (no prior snapshot); last_release is the repo's newest non-prerelease GitHub release "
                                "(in a monorepo, the newest one tagged with the tool's own package name); releases_30d counts non-draft releases in the 30 days before fetched_at, "
                                "out of the newest 20 (releases_30d_capped: all 20 fell inside the 30 days)",
                      "weeks": f"the tracked package's downloads in the {WEEKS} ISO weeks (Monday starts) ending with the week that holds window.last7's last day; "
                               "downloads sums the days observed up to that day, days counts them, partial = fewer than 7; a week with none is null, never 0. "
                               "npm writes 0 for days it has no data for, so an npm 0 counts as not observed. PyPI weeks come from the same pypistats response as pypi_7d; "
                               "npm weeks from a fixed-date range request",
                      "packages": "tracked is the package the page measures (data/universe.json; only the owner changes it). primary is chosen by rule: only-package; "
                                  "readme-install-line (the first install command in the tool's GitHub README naming one of its packages); highest-downloads "
                                  "(most downloads in window.last7, only when every candidate was observed); else null with the reason. Siblings are listed, never summed"},
            "tools": tools, "lanes": lanes}

def build_from_raw(raw=None, universe_path=UNIVERSE):
    """Rebuild from one run file (default: the newest in data/movers-raw/)."""
    r = Raw(raw or latest_run(RAW))
    return build(json.loads(pathlib.Path(universe_path).read_text()), r.fetch, r.run), r.used

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="rebuild data/movers.json purely from the newest run in data/movers-raw/")
    a = ap.parse_args(argv)
    if not a.offline:
        fetch, run, saved = recording()
        build(json.loads(UNIVERSE.read_text()), fetch, run)                  # fetch every response once
        dead = dead_hosts(saved)
        if dead:
            print(f"KEPT the previous run: every request to {', '.join(dead)} failed this time ({len(saved)} responses not saved)", file=sys.stderr)
        else:
            new = RAW / f"{datetime.now(timezone.utc):%Y-%m-%d}.json.gz"
            save_run(saved, new)
            for p in RAW.iterdir():                                          # one run is the record; git keeps the older ones
                if p != new:
                    p.unlink()
    movers, used = build_from_raw(latest_run(RAW), UNIVERSE)                 # the output always comes from the saved run
    OUT.write_text(dumps(movers))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(movers['tools'])} tools, window {movers['window']}, {len(used)} saved responses")
    return 0

if __name__ == "__main__":
    sys.exit(main())
