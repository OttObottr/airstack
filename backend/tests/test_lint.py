# spec: AS-280 AS-331
"""Lines held by tools, not by review: no SQL is built from strings, the page depends on no package, and no inline script runs."""
import pathlib, re, shutil, subprocess
import pytest
from airstack import paths
ROOT = paths.ROOT
def test_no_sql_is_built_from_strings():
    ruff = shutil.which("ruff") or str(ROOT / ".venv" / "bin" / "ruff")
    if not pathlib.Path(ruff).exists():
        pytest.skip("ruff is not installed (CI installs it from requirements-dev.txt)")
    out = subprocess.run([ruff, "check", "backend", "tools", "worker"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout[-2000:]

def test_the_page_has_no_package_dependencies():
    """Nothing is installed to build or run the page: no package manifest, lockfile or npm config; assembly and CI never call a package
    manager; every module imports only files of its own, by relative path."""
    assert not [f for f in ("package.json", "package-lock.json", ".npmrc", "vite.config.js") if (ROOT / f).exists()]
    ci, assemble = (ROOT / ".github" / "workflows" / "ci.yml").read_text(), (ROOT / "tools" / "assemble.sh").read_text()
    assert not re.search(r"\b(npm|npx|yarn|pnpm|node_modules)\b", ci + assemble)
    src = ROOT / "web" / "src"
    imports = [(p, m) for p in src.rglob("*.js") for m in re.findall(r"""^\s*(?:import\s+(?:[^'"=]*?\s+from\s+)?|export\s+[^'"=]*?\s+from\s+)['"]([^'"]+)['"]""", p.read_text(), re.M)]
    assert len(imports) > 50 and not [(p.name, m) for p, m in imports if not m.startswith(".") or not (p.parent / m).resolve().is_file()]

def test_public_ci_stays_on_free_standard_runners_and_stores_no_artifacts():
    """This public repository's standard runners are free; a larger runner or stored artifact would create a new billing surface."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    runners = re.findall(r"(?m)^\s*runs-on:\s*(\S+)", ci)
    assert runners and set(runners) == {"ubuntu-latest"}
    assert not re.search(r"actions/(?:upload-artifact|cache)@|\bcache:\s", ci)

def test_no_inline_script_runs_and_every_script_comes_from_this_origin():
    """The CSP allows scripts from this origin only: never 'unsafe-inline', 'unsafe-eval', a hash or another host. The page carries no inline
    script (structured data is not a script), and every script it names is a file it ships."""
    csp = next(l for l in (ROOT / "web" / "public" / "_headers").read_text().splitlines() if l.strip().startswith("Content-Security-Policy:"))
    assert re.search(r"script-src ([^;]+)", csp).group(1).split() == ["'self'"]
    page = (ROOT / "web" / "index.html").read_text()
    scripts = re.findall(r"<script\b([^>]*)>", page, re.I)
    assert all("src=" in a or 'type="application/ld+json"' in a for a in scripts), scripts
    assert sorted(re.findall(r'<script[^>]* src="([^"]+)"', page)) == ["site-data.js", "src/main.js"]


def test_no_assertion_is_always_true():
    """A test that cannot fail proves nothing: no `or True`, `assert True` or `if False` guard anywhere in the tests or journeys."""
    files = [p for p in [*sorted((ROOT / "backend" / "tests").glob("*.py")), *sorted((ROOT / "JOURNEY").glob("*.py"))] if p.name != "test_lint.py"]   # this file names the patterns
    bad = [f"{p.name}:{i}" for p in files for i, l in enumerate(p.read_text().splitlines(), 1)
           if re.search(r"\bor True\b|\bassert True\b|\bif False\b", l.split("#")[0]) and "re.search" not in l]
    assert not bad, bad
