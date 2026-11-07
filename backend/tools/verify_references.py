# spec: AS-013 AS-D01
"""Re-fetch every REAL evidence row's URL and confirm (1) it resolves and (2) the page actually contains the phrase the claim rests on.
Usage: python tools/verify_references.py [--offline] [--record]    (exit 1 if any reference is broken)
--record: when EVERY reference is valid, stamp the real re-read time on the facts behind the live answers (sync_checks), so a live answer shows the date its page was actually re-read, never the replay clock. A broken reference stamps nothing."""
import html, json, re, subprocess, sys
from datetime import datetime, timezone
from airstack import paths

ROOT = paths.ROOT
def normalize(text):
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()

def contains(page_text, phrase):
    return normalize(phrase) in normalize(page_text)

def load_site_data():
    js = "global.window={};require(%r);console.log(JSON.stringify(window.AIRSTACK_DATA))" % str(paths.SITE_DATA)
    return json.loads(subprocess.check_output(["node", "-e", js], text=True))

def load_rows():
    """Every sourced fact the page shows (Sources view, answer cards and the step captions all cite these same rows)."""
    data = load_site_data()
    return [("fireflies", {"id": f"{s['key']}@{s['url'][:40]}", **s}) for s in data["sources"] if s.get("real")]

def fetch(url):
    from airstack.fetch import get   # one honest name; robots.txt obeyed (AS-274)
    status, body, _ = get("https://" + url)
    return status, body

def main(offline=False, record=False):
    bad, keys = 0, set()
    for tool, e in load_rows():
        url, expect = e.get("url"), e.get("expect")
        if not url or not expect:
            print(f"FAIL  {tool}/{e['id']}: real row lacks url or expected phrase"); bad += 1; continue
        if offline:
            print(f"ok    {tool}/{e['id']}: structure"); continue
        try:
            status, body = fetch(url)
            ok = status == 200 and contains(body, expect)
            print(f"{'ok   ' if ok else 'FAIL '} {tool}/{e['id']}: HTTP {status} · phrase {'found' if ok else 'NOT FOUND'} · {url[:70]}")
            bad += 0 if ok else 1
            if ok: keys.add(e["key"])
        except Exception as ex:
            print(f"FAIL  {tool}/{e['id']}: {type(ex).__name__}: {ex} · {url[:70]}"); bad += 1
    print("\nRESULT:", "all references valid" if not bad else f"{bad} reference(s) invalid")
    if record and not offline and not bad:
        from airstack.store import Store
        store, now = Store(str(paths.DEMO_DB)), datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for k in sorted(keys): store.touch_check(k, now)
        print(f"recorded a real re-read at {now} for {len(keys)} fact(s): {sorted(keys)}")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main("--offline" in sys.argv, "--record" in sys.argv))
