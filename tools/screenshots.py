# spec: AS-130
"""Screenshots of every surface and state, from ONE build, for reviewers.
Usage: .venv/bin/python tools/screenshots.py <base_url> <out_dir>      (e.g. https://airstack.bot/ review/screenshots)
Reduced motion is on, so every state is the recorded one, not a frame mid-animation. Writes INDEX.md beside the images."""
import sys, pathlib
from playwright.sync_api import sync_playwright

VIEWPORTS = (("desktop-1440x900", {"viewport": {"width": 1440, "height": 900}}),
             ("mobile-390x844", {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True, "device_scale_factor": 2}))

def shots(base, out):
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True); rows = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        for vp, kw in VIEWPORTS:
            ctx = b.new_context(reduced_motion="reduce", service_workers="block", **kw); pg = ctx.new_page(); errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(base); pg.wait_for_selector("#trend .lb button"); pg.wait_for_timeout(300)
            def snap(name, what, el=None):
                f = out / f"{len(rows) + 1:02d}-{vp}-{name}.png"
                if el: pg.locator(el).scroll_into_view_if_needed(); pg.wait_for_timeout(150); pg.locator(el).screenshot(path=str(f))
                else: pg.screenshot(path=str(f))
                rows.append((f.name, what))
            def search(text, enter=True):
                pg.fill("#q", text)
                if enter: pg.press("#q", "Enter"); pg.wait_for_timeout(400)
            snap("landing", "Landing: the claim, one action, the provenance line")
            snap("check-browse", "Check yours: search, category bar, trending this week", "#check")
            search("pinec", enter=False); pg.wait_for_selector("#ta li"); snap("typeahead", "Search suggests as you type", "#check")
            pg.press("#q", "Enter"); pg.wait_for_selector("#toolcard .tiles"); pg.wait_for_timeout(300); snap("tool-page", "A tracked tool: tiles, peer chart, its own pages' facts", "#check")
            search("Blender"); pg.wait_for_selector("#toolcard dl.kv"); pg.wait_for_timeout(300); snap("listing", "A directory listing: Wikidata's record, linked, and own-page facts once researched", "#check")
            pg.click("#change"); pg.click("#alltypes"); pg.wait_for_selector("#trend .tl button"); pg.wait_for_timeout(300); snap("taxonomy", "Every software type, from software down, with counts", "#check")
            search("fathom"); pg.wait_for_selector("#answer .aw"); snap("tool-fathom", "Another assessed tool, online by default", "#check")
            search("zzzz-not-a-tool"); pg.wait_for_selector("#nf:not([hidden])"); snap("not-tracked", "A tool we do not track: said plainly, nothing left over from the last answer", "#check")
            pg.goto(base); pg.wait_for_selector("#movers"); snap("movers", "Moving this week: every number links its source", "#movers")
            if pg.locator("#vendors [data-chain]").count():
                pg.locator("#vendors [data-chain]").first.click(); pg.wait_for_selector("#chainTbl tbody tr"); snap("evidence-chain", "Evidence chain: each verified fact, its source, its re-check", "#chainSec")
            pg.goto(base); pg.wait_for_selector("#market"); snap("market", "The market: every cell verified on its page or 'Not observed'", "#market")
            assert not errors, errors; ctx.close()
        b.close()
    (out / "INDEX.md").write_text("# Screenshots\n\n" + "\n".join(f"- `{n}`: {w}" for n, w in rows) + "\n")
    return rows

if __name__ == "__main__":
    print(f"{len(shots(sys.argv[1], sys.argv[2]))} screenshots")
