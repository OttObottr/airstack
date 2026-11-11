"""Fail unless production serves this commit: version.json is HEAD and the selected files are byte-identical.
Usage: python tools/verify_deploy.py [https://airstack.bot/]"""
import hashlib
import json
import pathlib
import random
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from airstack import paths

ROOT = paths.ROOT
FILES = ("index.html", "insights/index.html", "method/index.html", "sw.js", "manifest.webmanifest", "robots.txt", "llms.txt",
         *paths.config("published-files")["files"])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


opener = urllib.request.build_opener(NoRedirect)
NOT_COMPARED = "fonts/ and icons/ (binary assets), _headers (checked by the live header tests)"

def live(base, name):
    url = base + ("" if name == "index.html" else name) + f"?c={random.randrange(10**9)}"
    req = urllib.request.Request(url, headers={"User-Agent": "airstack-verify-deploy", "Accept-Encoding": "identity"})
    for attempt in (1, 2):  # one retry: the edge can stall right after a deploy
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except (TimeoutError, ConnectionResetError, urllib.error.HTTPError) as ex:
            if attempt == 2 or (isinstance(ex, urllib.error.HTTPError) and ex.code < 500):
                raise RuntimeError(f"{url}: {ex}") from ex

def differences(base="https://airstack.bot/"):
    out = []
    plain = "http://" + base.split("://", 1)[1]
    try:
        req = urllib.request.Request(plain, headers={"User-Agent": "airstack-verify-deploy"})
        opener.open(req, timeout=30)
        out.append(f"{plain}: serves duplicate HTTP content instead of redirecting to HTTPS")
    except urllib.error.HTTPError as ex:
        if ex.code != 301 or not ex.headers.get("Location", "").startswith("https://"):
            out.append(f"{plain}: expected a 301 redirect to HTTPS, got {ex.code} {ex.headers.get('Location', '')}")
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    if subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT).stdout.strip():
        out.append("this checkout has uncommitted changes: compare a clean commit")
    deployed = json.loads(live(base, "version.json")).get("commit")
    if deployed != head:
        out.append(f"version.json: production runs {deployed}, this checkout is {head}")
    site = pathlib.Path(tempfile.mkdtemp(prefix="airstack-site-"))
    subprocess.run([str(ROOT / "tools" / "assemble.sh"), str(site)], check=True, cwd=ROOT)
    pages = sorted((site / "p").glob("*/index.html"))
    sample = tuple(p.relative_to(site).as_posix() for p in pages[::max(1, len(pages) // 2)][:3])
    shipped = FILES + sample + tuple(sorted(f.relative_to(site).as_posix() for f in (site / "src").rglob("*.js")))
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
