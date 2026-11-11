"""The logos that ship with the site, and /legal/logos.html, the credits page for the ones whose licence asks for credit.

Used by tools/assemble.sh. A logo ships only as a PNG or JPEG that logos.json names, under logos/<16 hex>.png or .jpg, within the size limits below;
logos.json is rewritten to name only what shipped. Credits come from each file's Commons record (data/site/logos.json, built by
airstack-ops tools/build_logos.py); email addresses and markup in author fields are not published."""
import html
import json
import re

NAME = re.compile(r"logos/[0-9a-f]{16}\.(png|jpg)")
PNG = b"\x89PNG\r\n\x1a\n"
JPEG = b"\xff\xd8\xff"
MAX_LOGO, MAX_LOGOS = 200_000, 40_000_000


def author(raw):
    """A Commons author field as plain text: no markup, no email addresses."""
    text = re.sub(r"<[^>]*>", " ", raw or "")
    text = re.sub(r"\(?\s*[\w.+-]+@[\w-]+(\.[\w-]+)+\s*\)?", " ", text)
    text = re.sub(r"\(\s*\)", " ", text)
    text = re.sub(r"\s+([,;])", r"\1", text)
    return " ".join(text.split()).strip(" ,;") or "see the file page"


def ship(site, out):
    """Copy the logos logos.json names into out/, check each, and rewrite out/logos.json to what shipped. Returns the kept map."""
    meta = json.loads((site / "logos.json").read_text())
    kept, total = {}, 0
    for pid, rel in sorted(meta["logos"].items()):
        src = site / rel
        if not NAME.fullmatch(rel) or not src.is_file():
            continue
        body = src.read_bytes()
        magic = PNG if rel.endswith(".png") else JPEG
        if not body.startswith(magic) or len(body) > MAX_LOGO:
            raise SystemExit(f"refusing logo {rel}: not the image its name says, within {MAX_LOGO} bytes")
        dst = out / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(body)
            total += len(body)
        kept[pid] = rel
    if total > MAX_LOGOS:
        raise SystemExit(f"logos exceed {MAX_LOGOS} bytes")
    credits = {pid: c for pid, c in meta["credits"].items() if pid in kept}
    (out / "logos.json").write_text(json.dumps({"source": meta["source"], "logos": kept}, separators=(",", ":")) + "\n")
    return kept, credits


def page(credits, names):
    """The credits page: one row per attribution-licensed logo, by product name."""
    e = html.escape
    rows = []
    for pid, (title, file_url, who, licence, licence_url) in sorted(credits.items(), key=lambda kv: (names.get(kv[0], kv[0]).lower(), kv[0])):
        rows.append(f'<tr><td>{e(names.get(pid, pid))}</td><td><a href="{e(file_url)}" rel="noopener">{e(title)}</a></td>'
                    f'<td>{e(author(who))}</td><td><a href="{e(licence_url or file_url)}" rel="noopener">{e(licence)}</a></td></tr>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Logo credits · AirStack</title><meta name="description" content="Credits for the logos shown on AirStack."><link rel="canonical" href="https://airstack.bot/legal/logos.html">
<meta name="robots" content="noindex"><link rel="icon" href="/icons/icon-192.png">
<style>:root{{color-scheme:dark;--color-bg:#07090B;--color-ink:#F4F6F8}}body{{margin:0;background:var(--color-bg);color:var(--color-ink);font:15px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}}main{{max-width:960px;margin:0 auto;padding:40px 20px 64px}}
a{{color:var(--color-ink);text-decoration-color:rgba(255,255,255,.3);text-underline-offset:3px}}h1{{font-size:32px;letter-spacing:-.02em;margin:16px 0 8px}}p{{color:color-mix(in oklab,var(--color-ink) 82%,transparent);max-width:68ch}}
.t{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{text-align:left;padding:6px 10px 6px 0;border-bottom:1px solid rgba(255,255,255,.1);vertical-align:top;overflow-wrap:anywhere}}th{{font-weight:600}}nav a{{font-size:14px}}</style></head>
<body><main><nav><a href="/">AirStack</a> · <a href="/legal/">Terms and privacy</a></nav>
<h1>Logo credits</h1>
<p>Logos identify the product or maker they belong to and appear only next to its name. Each comes from Wikimedia Commons under the licence on its file page, shown at icon size and otherwise unchanged. Logos whose licence asks for credit are listed below; the rest are public domain or CC0. Names and logos remain their owners’ marks, and their use here implies no endorsement.</p>
<p>To ask for a logo to be removed, write to <a href="mailto:privacy@airstack.bot">privacy@airstack.bot</a>.</p>
<div class="t"><table><tr><th>Product</th><th>File</th><th>Author</th><th>Licence</th></tr>
{chr(10).join(rows)}
</table></div>
</main></body></html>
"""
