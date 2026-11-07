# spec: AS-202 AS-256
"""Fail unless production serves the commit checked out here: version.json is HEAD and every selected public file is byte-identical.
Usage: python tools/verify_deploy.py [https://airstack.bot/]      (exit 1 on any difference; the release skill runs it last)"""
import hashlib, json, pathlib, random, subprocess, sys, tempfile, urllib.error, urllib.request
from airstack import paths

ROOT = paths.ROOT
FILES = ("index.html", "site-data.js", "market-data.js", "chain-data.json", "directory.json", "profiles.json", "pricing.json", "oss.json", "insights.json", "hf.json", "category-guides.json", "freshness.json", "news.json", "events.json", "stats.svg", "p/notion/index.html", "p/higgsfield/index.html", "sw.js", "manifest.webmanifest", "robots.txt", "sitemap.xml", "llms.txt")
NOT_COMPARED = "fonts/ and icons/ (binary assets), _headers (checked by the live header tests)"

def live(base, name):
    url = base + ("" if name == "index.html" else name) + f"?c={random.randrange(10**9)}"
    req = urllib.request.Request(url, headers={"User-Agent": "airstack-verify-deploy", "Accept-Encoding": "identity"})
    for attempt in (1, 2):                                                                    # the edge can stall for a moment right after a deploy: one retry, never more
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except (TimeoutError, ConnectionResetError, urllib.error.HTTPError) as ex:
            if attempt == 2 or (isinstance(ex, urllib.error.HTTPError) and ex.code < 500):
                raise RuntimeError(f"{url}: {ex}") from ex

def differences(base="https://airstack.bot/"):
    out = []
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    if subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT).stdout.strip():
        out.append("this checkout has uncommitted changes: compare a clean commit")
    deployed = json.loads(live(base, "version.json")).get("commit")
    if deployed != head:
        out.append(f"version.json: production runs {deployed}, this checkout is {head}")
    site = pathlib.Path(tempfile.mkdtemp(prefix="airstack-site-"))
    subprocess.run([str(ROOT / "tools" / "assemble.sh"), str(site)], check=True, cwd=ROOT)        # the site this commit builds, exactly as deploy.sh ships it
    shipped = FILES + tuple(sorted(f.relative_to(site).as_posix() for f in (site / "src").rglob("*.js")))   # every module the page loads, as assembled
    for name in shipped:
        local, served = (site / name).read_bytes(), live(base, name)
        if hashlib.sha256(local).digest() != hashlib.sha256(served).digest():
            out.append(f"{name}: production differs from this checkout ({len(served)} bytes served, {len(local)} local)")
    return out

if __name__ == "__main__":
    diffs = differences(sys.argv[1] if len(sys.argv) > 1 else "https://airstack.bot/")
    print("\n".join(diffs) if diffs else f"production runs this commit: version.json matches HEAD, {len(FILES)} files and every page module byte-identical")
    print(f"not compared: {NOT_COMPARED}")
    sys.exit(1 if diffs else 0)
