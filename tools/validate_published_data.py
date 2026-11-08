"""Validate a downloaded snapshot before it replaces data/site: the manifest is untrusted and nothing is executed.
Usage: python tools/validate_published_data.py <dir>"""
import gzip
import hashlib
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET
from airstack.files import read_json

MAX_FILES = 128
MAX_FILE_BYTES = 20_000_000
MAX_TOTAL_BYTES = 64_000_000
ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = read_json(ROOT / "config" / "published-files.json")
PUBLIC_NAMES = set(POLICY["files"])
OPEN_RELEASE = re.compile(r"open-data/airstack-\d{4}-\d{2}\.jsonl\.gz")
JS_ASSIGNMENTS = {"site-data.js": "AIRSTACK_DATA", "market-data.js": "AIRSTACK_MARKET"}
FORBIDDEN_KEYS = {"__proto__", "constructor", "prototype"}
HASH = re.compile(r"[0-9a-f]{64}")
JS = re.compile(r"\A(?://[^\n]*\n)*window\.([A-Z0-9_]+)\s*=\s*(\{[\s\S]*\});\s*\Z")


def safe_name(name):
    path = pathlib.PurePosixPath(name)
    return (
        isinstance(name, str)
        and name == path.as_posix()
        and not path.is_absolute()
        and 1 <= len(path.parts) <= 4
        and all(part not in ("", ".", "..") and not part.startswith(".") for part in path.parts)
        and (name in PUBLIC_NAMES or OPEN_RELEASE.fullmatch(name))
    )


def no_dangerous_keys(value, where="$"):
    if isinstance(value, dict):
        bad = FORBIDDEN_KEYS.intersection(value)
        if bad:
            raise ValueError(f"{where}: forbidden object key {sorted(bad)[0]}")
        for key, child in value.items():
            no_dangerous_keys(child, f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            no_dangerous_keys(child, f"{where}[{index}]")


def parse_data(path):
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError(f"{path.name}: exceeds {MAX_FILE_BYTES} bytes")
    suffix = path.suffix.lower()
    if suffix == ".json":
        value = json.loads(raw)
        no_dangerous_keys(value)
    elif suffix == ".js":
        expected = JS_ASSIGNMENTS.get(path.name)
        if not expected:
            raise ValueError(f"{path.name}: JavaScript is not an approved data assignment")
        match = JS.fullmatch(raw.decode("utf-8"))
        if not match or match.group(1) != expected:
            raise ValueError(f"{path.name}: expected one window.{expected} JSON assignment")
        value = json.loads(match.group(2))
        no_dangerous_keys(value)
    elif suffix in {".atom", ".xml", ".svg"}:
        text = raw.decode("utf-8")
        if re.search(r"<!DOCTYPE|<!ENTITY|<script\b|<foreignObject\b|\bon\w+\s*=", text, re.I):
            raise ValueError(f"{path.name}: active or entity-bearing XML is not allowed")
        root = ET.fromstring(text)
        if suffix == ".svg" and not root.tag.endswith("svg"):
            raise ValueError(f"{path.name}: expected an SVG root")
    elif suffix == ".gz":
        expanded = 0
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, 1):
                expanded += len(line.encode())
                if expanded > MAX_TOTAL_BYTES:
                    raise ValueError(f"{path.name}: expanded data is too large")
                value = json.loads(line)
                no_dangerous_keys(value, f"line {line_no}")
    else:
        raw.decode("utf-8")
    return raw


def validate(root):
    root = pathlib.Path(root)
    manifest_path = root / "data-manifest.json"
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict) or not 1 <= len(manifest) <= MAX_FILES:
        raise ValueError(f"manifest must contain 1..{MAX_FILES} files")
    total = 0
    for name, wanted in manifest.items():
        if not safe_name(name) or not isinstance(wanted, str) or not HASH.fullmatch(wanted):
            raise ValueError(f"unsafe manifest entry: {name!r}")
        path = root / pathlib.PurePosixPath(name)
        if not path.is_file():
            raise ValueError(f"missing dataset: {name}")
        raw = parse_data(path)
        total += len(raw)
        if hashlib.sha256(raw).hexdigest() != wanted:
            raise ValueError(f"checksum mismatch: {name}")
    if total > MAX_TOTAL_BYTES:
        raise ValueError(f"dataset exceeds {MAX_TOTAL_BYTES} bytes")
    extra = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p != manifest_path and p.relative_to(root).as_posix() not in manifest)
    if extra:
        raise ValueError(f"files absent from manifest: {', '.join(extra[:3])}")
    return len(manifest), total


if __name__ == "__main__":
    try:
        count, size = validate(sys.argv[1])
        print(f"validated {count} files ({size} bytes)")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, ET.ParseError) as error:
        sys.exit(f"refused published data: {error}")
