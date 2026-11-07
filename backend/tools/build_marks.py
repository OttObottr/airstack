# spec: AS-270
"""marks.json: the logo Wikidata records (P154) for each company that makes a listed product and each product with a page, with the
licence of its file on Wikimedia Commons. Only these sources: no vendor favicon, no logo API.

A file is kept only under a free licence: public domain (PD-textlogo, a logo too simple for copyright, among them), CC0, CC BY or
CC BY-SA. Anything else, or a page with no machine-readable licence, is left out with its reason. A free copyright licence is not a
trademark licence: most marks are trademarks, and each one says so when Commons does. Images are not downloaded: marks.json holds each
file's Commons address with its licence, author and credit; whether a deploy self-hosts them is a separate decision.

The licence fields are the ones Commons' API reports as imageinfo extmetadata (LicenseShortName, LicenseUrl, Artist, Credit,
AttributionRequired, Restrictions). Commons derives them from hidden markers on the file's own page, and that page is what is read:
the API path is closed to AirStackBot by robots.txt, /wiki/File: pages are open. A logo with an end date on Wikidata is former, not used.

Each File: page is saved, kept to those markers, once per run (data/commons-raw/<date>.json.gz); items come from the same Wikidata
reads as firmographics (data/wikidata-entities-raw/). The build repeats offline, byte for byte. No model call.

Run the fetch after build_firmographics.py --fetch, never alongside it: both add to the same day's Wikidata file.

Usage: ../.venv/bin/python tools/build_marks.py --fetch    # read the items, then their logos' File: pages, then build
       ../.venv/bin/python tools/build_marks.py            # rebuild marks.json from what is saved"""
import argparse, hashlib, html, json, re, sys, urllib.parse
from concurrent.futures import ThreadPoolExecutor

import build_firmographics as bf
from build_firmographics import fetch
from airstack import paths

OUT, RAW = paths.MARKS, paths.DATA / "commons-raw"
PAGE, UPLOAD = "https://commons.wikimedia.org/wiki/File:", "https://upload.wikimedia.org/wikipedia/commons/"
FREE = re.compile(r"(?i)(public domain|cc0(?: 1\.0)?|cc by(?:-sa)? \d\.\d(?: [a-z]{2,3})?)")
KEPT = f"from each {PAGE}<name> page: its final address, the licence tables (licensetpl), the author and source rows (fileinfotpl), " \
       "the restriction templates and the categories; the rest of the page is dropped"

def scope():
    """The companies firmographics covers, and the directory products that have a page (a profile)."""
    profiles = json.loads(paths.PROFILES.read_text())
    products = {p[0] for p in json.loads(paths.DIRECTORY.read_text())["products"] if p[0] in profiles}
    return sorted(set(bf.makers()) | products)

def current_logo(item):
    """The logo Wikidata ranks best that has not ended (Google's 2015 logo ended in 2026: the 2026 one is used)."""
    return next((v for s in bf.statements(item, "P154") if "P582" not in (s.get("qualifiers") or {}) and isinstance(v := bf.value(s), str)), None)

def page(name):
    s, h, hdr = fetch.get(PAGE + urllib.parse.quote(name.replace(" ", "_")))
    row = lambda k: (m.group(1) if (m := re.search(rf'(?s)<td id="fileinfotpl(?:_|&#95;){k}"[^>]*>.*?</td>\s*<td[^>]*>(.*?)</td>', h)) else None)
    cats = re.search(r'"wgCategories":(\[.*?\])', h)
    return {"status": s, "read": bf.now(), "final": hdr.get("x-final-url"), "licences": re.findall(r'(?s)<table class="licensetpl".*?</table>', h),
            "author": row("aut"), "credit": row("src"), "restrictions": sorted(set(re.findall(r"\brestriction-([a-z-]+)", h))),
            "categories": json.loads(cats.group(1)) if cats else []}

def text(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip() or None

def field(table, k):
    m = re.search(rf'(?s)<span class="licensetpl(?:_|&#95;){k}"[^>]*>(.*?)</span>', table)
    return text(m.group(1)) if m else None

def upload_url(title):
    """Commons' own address for a file: /<md5[0]>/<md5[:2]>/<name>, from the name with underscores (no redirect, no API)."""
    t = title.replace(" ", "_"); h = hashlib.md5(t.encode()).hexdigest()
    return f"{UPLOAD}{h[0]}/{h[:2]}/{urllib.parse.quote(t)}"

def mark(name, p):
    """(the mark, None) when the file's page gives a free licence; (None, why not) otherwise."""
    if not p or p.get("status") != 200:
        return None, f"File: page not read (status {(p or {}).get('status')})"
    licences = [(field(t, "short"), t) for t in p["licences"]]
    if not licences:
        return None, "no machine-readable licence on the File: page"
    nonfree = lambda t: re.search(r'licensetpl(?:_|&#95;)nonfree"', t) and field(t, "nonfree") != "false"   # Commons' own non-free flag overrides the name
    free = next(((short, t) for short, t in licences if short and FREE.fullmatch(short) and not nonfree(t)), None)
    if not free:
        return None, "licence not on the free list: " + ", ".join(sorted({s or "unnamed" for s, _ in licences}))
    final = p.get("final") or ""
    title = urllib.parse.unquote(final.split("/wiki/File:", 1)[1]) if "/wiki/File:" in final else name   # a renamed file: its new name
    short, t = free
    return {"file": title.replace("_", " "), "page": PAGE + urllib.parse.quote(title.replace(" ", "_")), "url": upload_url(title), "licence": short,
            "licence_url": field(t, "link"), "basis": "PD-textlogo" if "PD textlogo" in p["categories"] else None,
            "author": text(p["author"]), "credit": text(p["credit"]), "attribution": field(t, "attr"),
            "attribution_required": field(t, "attr(?:_|&#95;)req") == "true", "trademarked": "trademarked" in p["restrictions"], "read": p["read"][:10]}, None

def fetch_pages(names):
    f, raw = bf.run_file(RAW, {"kept": KEPT, "pages": {}})
    todo = sorted(set(names) - set(raw["pages"]))
    with ThreadPoolExecutor(4) as ex:                                      # Wikimedia asks bots for fewer than ten requests in flight
        for i in range(0, len(todo), 400):
            raw["pages"].update(zip(todo[i:i + 400], ex.map(page, todo[i:i + 400]))); bf.save(f, raw)
            print(f"commons pages: {min(i + 400, len(todo))}/{len(todo)}", flush=True)
    return raw

def build():
    items, pages = bf.latest(bf.WD).get("items", {}), bf.latest(RAW).get("pages", {})
    marks, dropped, ids = {}, {}, scope()
    for q in ids:
        name = current_logo(items.get(q) or {})
        if name:
            m, why = mark(name, pages.get(name))
            if m:
                marks[q] = {k: v for k, v in m.items() if v is not None}
            else:
                dropped[q] = why
    reasons = {}
    for why in dropped.values():
        k = why.split(":")[0]; reasons[k] = reasons.get(k, 0) + 1
    data = {"source": {
        "name": "Wikimedia Commons, through each item's logo on Wikidata (P154)", "url": "https://commons.wikimedia.org/",
        "license": "each file's own, recorded with it; Wikidata's statements are CC0 1.0",
        "read": max((p["read"] for p in pages.values()), default="")[:10] or None,
        "policy": "Only files under a free licence (public domain including PD-textlogo, CC0, CC BY, CC BY-SA) are listed, never altered. A free copyright "
                  "licence is not a trademark licence: a mark flagged trademarked is shown only to name its owner's product. Not downloaded: url is "
                  "Commons' own address; marks are excluded from AirStack's code and data licences.",
        "how": "licence, author, credit and restrictions read from the hidden licence markers on each File: page, the fields Commons' API reports as "
               "imageinfo extmetadata (its API path is closed to bots by robots.txt)",
        "scope": f"{len(ids)} items:the companies that make a listed product and the directory products with a page",
        "dropped": dict(sorted(reasons.items()))},
        "marks": marks, "dropped": dropped}
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(body)
    print(f"marks.json: {len(marks)} marks ({sum(m.get('basis') == 'PD-textlogo' for m in marks.values())} PD-textlogo, "
          f"{sum(m['trademarked'] for m in marks.values())} trademarked), {len(dropped)} left out {reasons}; {len(body) // 1024} KB")

def main():
    a = argparse.ArgumentParser(); a.add_argument("--fetch", action="store_true"); args = a.parse_args()
    if args.fetch:
        ids = scope()
        _, raw = bf.fetch_items(ids)
        fetch_pages({n for q in ids if (n := current_logo(raw["items"].get(q) or {}))})
    build()

if __name__ == "__main__":
    sys.exit(main())
