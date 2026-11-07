# spec: AS-274
"""Small, durable file writes for generated artifacts.

A builder either replaces an artifact with a complete new value or leaves the old value byte-for-byte intact. Temporary files live
beside the destination so ``os.replace`` is atomic on the same filesystem.
"""
import os, tempfile
from pathlib import Path


def atomic_write_text(path, text, *, encoding="utf-8"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
