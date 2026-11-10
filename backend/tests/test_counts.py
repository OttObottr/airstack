"""Counting: the privacy notice lists exactly the fields the site sends, and the counting code's own tests pass."""
import json
import re
import shutil
import subprocess
import pytest
from conftest import ROOT


def test_the_privacy_notice_lists_exactly_the_fields_the_site_sends():
    schema = json.loads((ROOT / "worker" / "schema.json").read_text())["events"]
    sent = {t: sorted(k.rstrip("?") for k in f) for t, f in schema.items()}
    page = (ROOT / "web" / "public" / "legal" / "index.html").read_text()
    listed = {t: sorted(f.split()) for t, f in re.findall(r'data-event="(\w+)" data-fields="([\w ]+)"', page)}
    assert listed == sent


def test_the_counting_code_passes_its_tests():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "--test", "worker/index.test.js", "worker/beacon.test.js"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-1000:]
