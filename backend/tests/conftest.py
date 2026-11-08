"""Tests read the synthetic datasets in fixtures/site unless AIRSTACK_DATA names another data directory."""
import os
import pathlib
import subprocess
import sys

os.environ.setdefault("AIRSTACK_DATA", str(pathlib.Path(__file__).resolve().parent / "fixtures"))
from airstack import paths  # noqa: E402

ROOT = paths.ROOT
os.environ["PYTHONPATH"] = os.pathsep.join([str(ROOT / "backend"), str(ROOT / "backend" / "tools"), *filter(None, [os.environ.get("PYTHONPATH")])])


def pytest_sessionstart(session):
    subprocess.run([sys.executable, str(ROOT / "backend" / "tools" / "build_pages.py")], check=True, capture_output=True)
