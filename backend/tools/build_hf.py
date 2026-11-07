# spec: AS-259
"""Open models per job, from the Hugging Face Hub's public API (no token): for each pipeline tag, the most-downloaded, most-liked and
trending models, each with its downloads, likes, licence tag, last update and gating. Every raw response is saved with its endpoint,
query and time (data/hf-raw/), and the build repeats offline. No model call, no cost.

Usage:  ../.venv/bin/python tools/build_hf.py --fetch     # query the Hub (anonymous), save every response
        ../.venv/bin/python tools/build_hf.py             # rebuild hf.json offline from the saved responses"""
import argparse, gzip, json, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from airstack import paths
from airstack.fetch import UA

ROOT = paths.ROOT
RAW, OUT = paths.DATA / "hf-raw", paths.HF
API = "https://huggingface.co/api/models"
TASKS = {   # Hub pipeline tag -> the job in plain words
    "text-generation": "Text generation",
    "automatic-speech-recognition": "Speech to text",
    "text-to-speech": "Text to speech",
    "text-to-image": "Text to image",
    "text-to-video": "Text to video",
    "image-to-video": "Image to video",
    "feature-extraction": "Embeddings",
    "image-text-to-text": "Image and text to text",
}
SORTS = ["downloads", "likes", "trendingScore"]
# `full=false` is not honoured (it returns every file in the repo); expand[] asks for just the fields used here
EXPAND = ["author", "downloads", "likes", "lastModified", "gated", "tags", "pipeline_tag"]
TOP = 15

def fetch():
    RAW.mkdir(parents=True, exist_ok=True)
    for tag in TASKS:
        for sort in SORTS:
            f = RAW / f"{tag}--{sort}.json.gz"
            if f.exists():
                continue
            query = {"pipeline_tag": tag, "sort": sort, "direction": "-1", "limit": "40", "expand[]": EXPAND}
            req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(query, doseq=True)}", headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    items = json.load(r)
            except Exception as e:
                print("failed", tag, sort, str(e)[:120]); time.sleep(10); continue
            f.write_bytes(gzip.compress(json.dumps({"endpoint": API, "query": query, "sort": sort,
                                                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "items": items},
                                                   ensure_ascii=False, sort_keys=True).encode(), mtime=0))
            time.sleep(1)

def render():
    tasks, fetched = {t: {} for t in TASKS}, ""
    for f in sorted(RAW.glob("*.json.gz")):                                # downloads < likes < trendingScore: the downloads response wins
        d = json.loads(gzip.decompress(f.read_bytes())); tag = f.name.split("--")[0]; fetched = max(fetched, d["fetched_at"])
        for m in d["items"]:
            if "downloads" not in m:
                continue
            lic = next((t[len("license:"):] for t in m.get("tags", []) if t.startswith("license:")), None)
            tasks[tag].setdefault(m["id"], {"id": m["id"], "url": f"https://huggingface.co/{m['id']}", "author": m.get("author"),
                                            "downloads": m["downloads"], "likes": m.get("likes"), "license": lic,
                                            "updated": (m.get("lastModified") or "")[:10] or None,
                                            "gated": None if "gated" not in m else bool(m["gated"])})
    out = {"source": {"name": "Hugging Face Hub API", "url": API, "fetched_at": fetched,
                      "note": "Downloads are Hugging Face's own count for the last 30 days; likes are a current total. "
                              "A lead, not an endorsement: check each model's licence and terms."},
           "tasks": {t: {"name": TASKS[t], "models": sorted(v.values(), key=lambda m: (-m["downloads"], m["id"]))[:TOP]} for t, v in tasks.items()}}
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))

def build():
    OUT.write_text(render())
    out = json.loads(OUT.read_text())
    print(f"hf.json: {sum(len(t['models']) for t in out['tasks'].values())} models in {len(out['tasks'])} tasks (read {out['source']['fetched_at']})")

if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--fetch", action="store_true"); args = a.parse_args()
    if args.fetch:
        fetch()
    build()
