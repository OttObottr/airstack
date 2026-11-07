# spec: AS-248
"""Wikidata's public query service, as the directory and community builders use it: one query, its raw answer kept gzipped beside the
query and the time, so a rebuild repeats offline. A saved answer is reused unless refreshed, so an interrupted fetch resumes."""
import gzip
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .fetch import UA

ENDPOINT = "https://query.wikidata.org/sparql"


def q(binding, key):
    """The value of one variable in one result row, or None."""
    return (binding.get(key) or {}).get("value")


def qid(uri):
    """An item id from a Wikidata URI, or None. Only Q followed by digits passes, so nothing else ever reaches a VALUES block."""
    x = uri.rsplit("/", 1)[-1] if uri else None
    return x if x and re.fullmatch(r"Q\d+", x) else None


def sparql(raw_dir, name, query, refresh=False, tries=4):
    """Run one query (POST: some are long), keep the raw response in `raw_dir/<name>.json.gz`, return its result rows."""
    f = raw_dir / f"{name}.json.gz"
    if f.exists() and not refresh:
        return json.loads(gzip.decompress(f.read_bytes()))["results"]
    for attempt in range(tries):
        try:
            req = urllib.request.Request(ENDPOINT, data=urllib.parse.urlencode({"query": query}).encode(),
                                         headers={"Accept": "application/sparql-results+json", "User-Agent": UA,
                                                  "Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=170) as r:
                body = json.loads(r.read())
            break
        except Exception as ex:                                        # the public endpoint throttles: wait as long as it asks, then give up loudly
            if attempt == tries - 1:
                raise RuntimeError(f"{name}: {ex}") from ex
            wait = getattr(ex, "headers", None) and ex.headers.get("Retry-After")
            time.sleep(int(wait) if wait and str(wait).isdigit() else 20 * (attempt + 1))
    raw_dir.mkdir(parents=True, exist_ok=True)
    f.write_bytes(gzip.compress(json.dumps({"endpoint": ENDPOINT, "query": query, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                            "results": body["results"]["bindings"]}, ensure_ascii=False, sort_keys=True).encode(), mtime=0))
    time.sleep(1)
    return body["results"]["bindings"]
