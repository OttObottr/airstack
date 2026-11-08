"""Whole-file JSON and text I/O with atomic writes. A .gz path is gzip with mtime 0, so equal values give equal bytes."""
import gzip
import json
import os
import tempfile
from pathlib import Path

COMPACT = {"ensure_ascii": False, "separators": (",", ":")}


def atomic_write_text(path, text):
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def read_json(path):
    data = Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith(".gz") else data)


def write_json(path, value, end="", **dumps):
    """`dumps` are json.dumps options (COMPACT by default); `end` is appended."""
    data = (json.dumps(value, **(dumps or COMPACT)) + end).encode("utf-8")
    atomic_write_bytes(path, gzip.compress(data, mtime=0) if str(path).endswith(".gz") else data)
