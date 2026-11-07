# spec: AS-141 AS-210 AS-251 AS-255 AS-263 AS-265 AS-295 AS-298 AS-332 AS-365
from conftest import ROOT
import hashlib, http.server, json, os, pathlib, pytest, re, spec_audit, subprocess, sys, threading
from airstack import paths


# --- specs ---

def test_spec_audit_passes():
    assert spec_audit.main() == 0

def test_social_connectors_are_static_only_and_every_metered_source_is_off():
    c = json.loads((ROOT / "config/social-connectors.json").read_text())
    assert c["policy"]["public_runtime_fetches"] is False and c["policy"]["visitor_triggered_fetches"] is False
    assert c["policy"]["automatic_recharge"] is False
    assert {k for k, v in c["connectors"].items() if v["state"] == "build_only"} == {"github", "hacker_news"}
    assert all(c["connectors"][k]["state"] == "off" for k in ("reddit", "x", "threads", "exa", "muse_web_search"))


# --- data_not_in_repo: Data is not code: the repository tracks none, and the scripts that keep it safe really round-trip it. ---

def tracked():
    return subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).split()

def test_the_repository_tracks_code_and_configuration_only():
    files = tracked()
    assert not [f for f in files if f.startswith("data/")], "data/ is working data: it is ignored by git"
    assert not [f for f in files if f.endswith((".db", ".sqlite", ".jsonl.gz"))]
    assert not [f for f in files if "/" not in f and f.endswith((".json", ".js", ".atom", ".svg")) and f not in ("wrangler.jsonc", "sw.js")]   # no generated file at the root
    big = [(f, (ROOT / f).stat().st_size) for f in files if (ROOT / f).exists() and (ROOT / f).stat().st_size > 1_200_000]
    assert not big, f"a file this large is data, not code: {big}"

def run(script, env, *args):
    return subprocess.run(["bash", str(ROOT / "tools" / script), *args], cwd=ROOT, env={**os.environ, **env}, capture_output=True, text=True)

def test_a_backup_restores_every_file_byte_for_byte(tmp_path):
    data = tmp_path / "data"; (data / "site").mkdir(parents=True)
    (data / "airstack-market.db").write_bytes(os.urandom(4096)); (data / "site" / "profiles.json").write_text('{"a": 1}'); (data / "wikidata-raw").mkdir()
    (data / "wikidata-raw" / "2026-11-05.json.gz").write_bytes(os.urandom(512))
    done = run("backup.sh", {"AIRSTACK_DATA": str(data)}, str(tmp_path / "backups"))
    assert done.returncode == 0, done.stderr
    archive = next((tmp_path / "backups").glob("airstack-data-*.tar.gz")); assert (tmp_path / "backups" / (archive.name + ".sha256")).exists()
    restored = tmp_path / "restored"; restored.mkdir()
    subprocess.run(["tar", "-xzf", str(archive), "-C", str(restored)], check=True)
    for f in (p for p in data.rglob("*") if p.is_file()):
        assert (restored / f.relative_to(data)).read_bytes() == f.read_bytes(), f.name

class Prod(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

def serve(directory):
    handler = lambda *a, **k: Prod(*a, directory=str(directory), **k)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler); threading.Thread(target=server.serve_forever, daemon=True).start()
    return server

def test_data_pull_fetches_the_datasets_and_refuses_a_file_that_does_not_match_its_checksum(tmp_path):
    prod = tmp_path / "prod"; (prod / "open-data").mkdir(parents=True)
    files = {"profiles.json": b'{"a": 1}', "open-data/README.md": b"released data"}
    for name, body in files.items(): (prod / name).write_bytes(body)
    (prod / "data-manifest.json").write_text(json.dumps({n: hashlib.sha256(b).hexdigest() for n, b in files.items()}))
    manifest_hash = hashlib.sha256((prod / "data-manifest.json").read_bytes()).hexdigest()
    server = serve(prod); base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        ok = run("data_pull.sh", {"AIRSTACK_DATA": str(tmp_path / "pulled"), "AIRSTACK_MANIFEST_SHA256": manifest_hash}, base)
        assert ok.returncode == 0, ok.stderr
        assert all((tmp_path / "pulled" / "site" / n).read_bytes() == b for n, b in files.items())          # nested datasets included
        (prod / "profiles.json").write_bytes(b'{"a": 2}')                                                  # production serves something the manifest does not describe
        bad = run("data_pull.sh", {"AIRSTACK_DATA": str(tmp_path / "again"), "AIRSTACK_MANIFEST_SHA256": manifest_hash}, base)
    finally:
        server.shutdown()
    assert bad.returncode != 0 and "checksum mismatch: profiles.json" in bad.stderr

def test_data_pull_refuses_paths_outside_the_snapshot_and_executable_data(tmp_path):
    prod = tmp_path / "prod"; prod.mkdir()
    outside = tmp_path / "outside.txt"
    attack = b"owned"
    (prod / "data-manifest.json").write_text(json.dumps({"../outside.txt": hashlib.sha256(attack).hexdigest()}))
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

def test_the_scheduled_refresh_cannot_spend_pull_push_or_deploy():
    sh = (ROOT / "tools" / "daily.sh").read_text()
    forbidden = ("--live", "AIRSTACK_ACCOUNT_CAP_USD=", "git pull", "git push", "tools/deploy.sh", "wrangler deploy")
    executable = "\n".join(line for line in sh.splitlines() if not line.lstrip().startswith("#"))
    assert not [token for token in forbidden if token in executable]
    assert "lost-a-quote.txt" in sh and "review required" in sh

def test_assembly_refuses_an_ignored_dataset_symlink_before_copying_it(tmp_path):
    data = tmp_path / "data"; site = data / "site"; site.mkdir(parents=True)
    outside = tmp_path / "outside.js"; outside.write_text('window.AIRSTACK_DATA = {"meta":{}};\n')
    (site / "site-data.js").symlink_to(outside)
    out = tmp_path / "public"
    result = run("assemble.sh", {"AIRSTACK_DATA": str(data)}, str(out))
    assert result.returncode != 0 and "dataset symlink: site-data.js" in result.stderr and not out.exists()

def test_assembly_refuses_broad_or_symlinked_output_before_removing_anything(tmp_path):
    marker = tmp_path / "keep.txt"; marker.write_text("keep")
    for target in ("/", str(ROOT), str(pathlib.Path.home())):
        result = run("assemble.sh", {"AIRSTACK_DATA": str(tmp_path / "missing")}, target)
        assert result.returncode != 0 and "refusing unsafe assembly output" in result.stderr and marker.read_text() == "keep"
    real = tmp_path / "real"; real.mkdir()
    link = tmp_path / "redirect"; link.symlink_to(real, target_is_directory=True)
    redirected = run("assemble.sh", {"AIRSTACK_DATA": str(tmp_path / "missing")}, str(link / "out"))
    assert redirected.returncode != 0 and "symlinked path" in redirected.stderr and not (real / "out").exists()

def test_release_never_downloads_wrangler_and_requires_the_reviewed_binary():
    sh = (ROOT / "tools" / "deploy.sh").read_text()
    assert "npx" not in sh and "WRANGLER_VERSION=4.156.0" in sh and "WRANGLER_SHA256=" in sh
    assert "AIRSTACK_WRANGLER_JS" in sh and 'node "$AIRSTACK_WRANGLER_JS" deploy' in sh

def test_the_publish_allowlist_matches_the_snapshot_and_excludes_private_names():
    policy = json.loads((ROOT / "config" / "published-files.json").read_text())
    names = set(policy["files"])
    assert len(names) == len(policy["files"])
    assert not {"airstack-market.db", "airstack-demo.db", "brief.json", "corroboration.json", "pricing-pages.json"} & names
    manifest = paths.SITE / "data-manifest.json"
    if manifest.exists():
        assert hashlib.sha256(manifest.read_bytes()).hexdigest() == (ROOT / "config" / "published-data.sha256").read_text().strip()
    actual = {p.relative_to(paths.SITE).as_posix() for p in paths.SITE.rglob("*") if p.is_file() and p.name not in {".DS_Store", "data-manifest.json"}}
    monthly = {name for name in actual if re.fullmatch(r"open-data/airstack-\d{4}-\d{2}\.jsonl\.gz", name)}
    assert actual - monthly == names


# --- rebuilds: Every published dataset is exactly what its builder writes from the data already saved. No builder here reads the network ---

BUILDERS = [("build_events.py", paths.EVENTS), ("build_firmographics.py", paths.FIRMOGRAPHICS), ("build_graph.py", paths.GRAPH),
            ("build_insights.py", paths.INSIGHTS), ("build_marks.py", paths.MARKS), ("build_news.py", paths.NEWS),
            ("build_oss.py", paths.OSS), ("build_trust.py", paths.TRUST)]

@pytest.mark.private_data
@pytest.mark.parametrize("script, output", BUILDERS, ids=[s for s, _ in BUILDERS])
def test_the_published_file_is_what_its_builder_writes_from_the_saved_data(script, output):
    before = output.read_bytes()
    subprocess.run([sys.executable, str(paths.ROOT / "backend" / "tools" / script)], check=True, capture_output=True)
    assert output.read_bytes() == before, f"{output.name} is stale: run backend/tools/{script}"


def test_the_repository_root_stays_small():
    """AS-332: a reader opening the repository sees at most 15 entries (dotfiles aside)."""
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    assert len({t.split("/")[0] for t in tracked if not t.startswith(".")}) <= 15

