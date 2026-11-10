"""The repository: code and policy only, data scripts that round-trip safely, and lines held by tools rather than review."""
import ast
import hashlib
import http.server
import json
import os
import pathlib
import pytest
import re
import shutil
import subprocess
import sys
import threading
from conftest import ROOT
from airstack import paths


def tracked():
    return subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).split()

def test_the_repository_tracks_code_and_configuration_only():
    files = [f for f in tracked() if not f.startswith("backend/tests/fixtures/")]
    assert not [f for f in files if f.startswith("data/") or f.endswith((".db", ".sqlite", ".jsonl.gz"))]
    assert not [f for f in files if "/" not in f and f.endswith((".json", ".js", ".atom", ".svg")) and f != "wrangler.jsonc"]
    assert not [f for f in files if (ROOT / f).exists() and (ROOT / f).stat().st_size > 1_200_000]

def test_configuration_contains_policy_not_product_records():
    forbidden = {"homepage", "domain", "vendor", "aliases", "products", "entities", "focus_product", "subject", "examples", "renamed", "excluded"}
    def keys(value):
        if isinstance(value, dict):
            yield from value
            for child in value.values(): yield from keys(child)
        elif isinstance(value, list):
            for child in value: yield from keys(child)
    for path in (ROOT / "config").glob("*.json"):
        assert not (set(keys(json.loads(path.read_text()))) & forbidden), path.name

def test_code_contains_no_product_names():
    records = [*json.loads(paths.CATALOG.read_text()), *json.loads(paths.UNIVERSE.read_text())]
    names = {str(row.get(key, "")).casefold() for row in records for key in ("id", "name") if len(str(row.get(key, ""))) >= 4}
    names -= set(re.findall(r'"([^"]+)"', (ROOT / "config" / "pages.json").read_text().casefold()))
    hits = [f"{path.relative_to(ROOT)}:{node.lineno}"
            for path in [*(ROOT / "backend" / "airstack").rglob("*.py"), *(ROOT / "backend" / "tools").rglob("*.py"), *(ROOT / "tools").rglob("*.py")]
            for node in ast.walk(ast.parse(path.read_text()))
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.casefold() in names]
    assert not hits, hits

def run(script, env, *args):
    return subprocess.run(["bash", str(ROOT / "tools" / script), *args], cwd=ROOT, env={**os.environ, **env}, capture_output=True, text=True)

class Quiet(http.server.SimpleHTTPRequestHandler):
    agents = set()
    def log_message(self, *a): pass
    def do_GET(self):
        Quiet.agents.add(self.headers.get("User-Agent")); super().do_GET()

def serve(directory):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: Quiet(*a, directory=str(directory), **k))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server

def test_data_pull_fetches_the_datasets_and_refuses_a_file_that_does_not_match_its_checksum(tmp_path):
    prod = tmp_path / "prod"; (prod / "open-data").mkdir(parents=True)
    files = {"profiles.json": b'{"a": 1}', "open-data/README.md": b"released data"}
    for name, body in files.items(): (prod / name).write_bytes(body)
    (prod / "data-manifest.json").write_text(json.dumps({n: hashlib.sha256(b).hexdigest() for n, b in files.items()}))
    manifest_hash = hashlib.sha256((prod / "data-manifest.json").read_bytes()).hexdigest()
    server = serve(prod); base = f"http://127.0.0.1:{server.server_address[1]}"; Quiet.agents.clear()
    try:
        ok = run("data_pull.sh", {"AIRSTACK_DATA": str(tmp_path / "pulled"), "AIRSTACK_MANIFEST_SHA256": manifest_hash}, base)
        assert ok.returncode == 0, ok.stderr
        assert all((tmp_path / "pulled" / "site" / n).read_bytes() == b for n, b in files.items())
        assert Quiet.agents == {"airstack-data/1"}
        (prod / "profiles.json").write_bytes(b'{"a": 2}')
        bad = run("data_pull.sh", {"AIRSTACK_DATA": str(tmp_path / "again"), "AIRSTACK_MANIFEST_SHA256": manifest_hash}, base)
    finally:
        server.shutdown()
    assert bad.returncode != 0 and "checksum mismatch: profiles.json" in bad.stderr

def test_data_pull_refuses_paths_outside_the_snapshot_and_executable_data(tmp_path):
    prod = tmp_path / "prod"; prod.mkdir()
    outside = tmp_path / "outside.txt"
    (prod / "data-manifest.json").write_text(json.dumps({"../outside.txt": hashlib.sha256(b"owned").hexdigest()}))
    server = serve(prod); base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        escaped_hash = hashlib.sha256((prod / "data-manifest.json").read_bytes()).hexdigest()
        escaped = run("data_pull.sh", {"AIRSTACK_DATA": str(tmp_path / "pulled"), "AIRSTACK_MANIFEST_SHA256": escaped_hash}, base)
        assert escaped.returncode != 0 and "unsafe path" in escaped.stderr and not outside.exists()
        payload = b'window.AIRSTACK_DATA={"ok":true}; fetch("https://outside.invalid")'
        (prod / "site-data.js").write_bytes(payload)
        (prod / "data-manifest.json").write_text(json.dumps({"site-data.js": hashlib.sha256(payload).hexdigest()}))
        active_hash = hashlib.sha256((prod / "data-manifest.json").read_bytes()).hexdigest()
        active = run("data_pull.sh", {"AIRSTACK_DATA": str(tmp_path / "active"), "AIRSTACK_MANIFEST_SHA256": active_hash}, base)
    finally:
        server.shutdown()
    assert active.returncode != 0 and "expected one window.AIRSTACK_DATA JSON assignment" in active.stderr

def test_assembly_refuses_a_dataset_symlink_before_copying_it(tmp_path):
    site = tmp_path / "data" / "site"; site.mkdir(parents=True)
    outside = tmp_path / "outside.js"; outside.write_text('window.AIRSTACK_DATA = {"meta":{}};\n')
    (site / "site-data.js").symlink_to(outside)
    result = run("assemble.sh", {"AIRSTACK_DATA": str(tmp_path / "data")}, str(tmp_path / "public"))
    assert result.returncode != 0 and "dataset symlink: site-data.js" in result.stderr and not (tmp_path / "public").exists()

def test_assembly_refuses_broad_or_symlinked_output_before_removing_anything(tmp_path):
    marker = tmp_path / "keep.txt"; marker.write_text("keep")
    for target in ("/", str(ROOT), str(pathlib.Path.home())):
        result = run("assemble.sh", {"AIRSTACK_DATA": str(tmp_path / "missing")}, target)
        assert result.returncode != 0 and "refusing unsafe assembly output" in result.stderr and marker.read_text() == "keep"
    real = tmp_path / "real"; real.mkdir()
    link = tmp_path / "redirect"; link.symlink_to(real, target_is_directory=True)
    redirected = run("assemble.sh", {"AIRSTACK_DATA": str(tmp_path / "missing")}, str(link / "out"))
    assert redirected.returncode != 0 and "symlinked path" in redirected.stderr and not (real / "out").exists()

def test_the_publish_allowlist_is_present_and_excludes_private_names():
    names = json.loads((ROOT / "config" / "published-files.json").read_text())["files"]
    assert len(names) == len(set(names))
    assert not [n for n in names if n.endswith((".db", ".sqlite"))]
    assert all((paths.SITE / n).is_file() for n in names)

def test_an_atomic_write_failure_preserves_the_previous_file(tmp_path, monkeypatch):
    import airstack.files as files
    out = tmp_path / "pricing.json"; out.write_bytes(b"previous")
    monkeypatch.setattr(files.os, "replace", lambda source, target: (_ for _ in ()).throw(OSError("interrupted")))
    with pytest.raises(OSError):
        files.atomic_write_text(out, "partial")
    assert out.read_bytes() == b"previous" and list(tmp_path.iterdir()) == [out]

def test_the_env_file_is_ignored_and_never_tracked():
    assert subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", ".env"]).returncode == 0
    assert ".env" not in tracked()

def test_ruff_passes():
    ruff = shutil.which("ruff") or str(pathlib.Path(sys.executable).parent / "ruff")
    if not pathlib.Path(ruff).exists():
        pytest.skip("ruff is not installed")
    out = subprocess.run([ruff, "check", "backend", "tools"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout[-2000:]

def test_every_script_comes_from_this_origin():
    csp = next(ln for ln in (ROOT / "web" / "public" / "_headers").read_text().splitlines() if ln.strip().startswith("Content-Security-Policy:"))
    assert re.search(r"script-src ([^;]+)", csp).group(1).split() == ["'self'"]
    page = (ROOT / "web" / "index.html").read_text()
    assert all("src=" in a or 'type="application/ld+json"' in a for a in re.findall(r"<script\b([^>]*)>", page, re.I))
    assert sorted(re.findall(r'<script[^>]* src="([^"]+)"', page)) == ["site-data.js", "src/main.js"]


def test_vendored_modules_are_the_pinned_bytes_and_import_only_each_other():
    import hashlib
    lock = json.loads((ROOT / "config" / "vendor.json").read_text())["modules"]
    vendor = ROOT / "web" / "src" / "vendor"
    assert {f.stem for f in vendor.glob("*.js")} == set(lock)
    for name, m in lock.items():
        body = (vendor / f"{name}.js").read_bytes()
        assert hashlib.sha256(body).hexdigest() == m["sha256"], name
        assert m["url"] == f"https://cdn.jsdelivr.net/npm/{name}@{m['version']}/+esm"
        imports = re.findall(rb'(?:from|import)\s*"([^"]+)"', body)
        assert all(i.startswith(b"./") and i[2:-3].decode() in lock for i in imports), (name, imports)   # no runtime CDN
