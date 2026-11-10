"""stats.svg: the headline counts and the week's movers as one embeddable image, animated with CSS only.
Usage: python backend/tools/build_stats.py"""
import html
from datetime import date
from airstack import paths

e = lambda s: html.escape(str(s), quote=True)
n = lambda v: f"{v:,}"

def day(s):
    d = date.fromisoformat(s[:10]); return f"{d.day} {d:%b %Y}"

def main():
    site = paths.read_js(paths.SITE_DATA)
    c = site["meta"]["counts"]
    tiles = [(c["products"], "software products"), (c["organizations"], "organizations"),
             (c["researched_products"], "read from their own pages"), (c["list_prices"], "list prices, quoted")]
    mt = site["moversTop"]; w = mt["window"]["last7"]
    rows = sorted((r for r in mt["rows"] if r["dl"].get("vsBase") is not None), key=lambda r: -r["dl"]["vsBase"])
    def item(r, x):
        v = r["dl"]["vsBase"]; up = v >= 0; name = r["name"] if len(r["name"]) <= 17 else r["name"][:16] + "…"
        return (f'<text x="{x}" y="0" class="tk"><tspan class="nm">{e(name)}</tspan><tspan dx="8" class="{"up" if up else "dn"}">'
                f'{"▲" if up else "▼"} {"+" if up else ""}{v:.1f}%</tspan></text>')
    width = lambda r: 9 * min(len(r["name"]), 17) + 9 * len(f'{r["dl"]["vsBase"]:+.1f}') + 64  # about 9 px a character, plus the arrow and a gap
    xs = [sum(width(x) for x in rows[:i]) for i in range(len(rows))]
    strip = "".join(item(r, x) for r, x in zip(rows, xs))
    span = max(1, sum(width(r) for r in rows))
    cols = "".join(f'<g transform="translate({48 + i * 280},150)"><text class="big" y="0">{n(v)}</text><text class="lab" y="30">{e(ln)}</text></g>'
                   for i, (v, ln) in enumerate(tiles))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 300" width="1200" height="300" role="img" aria-labelledby="t d">
<title id="t">AirStack: {n(tiles[0][0])} software products, {n(tiles[2][0])} read from their own pages</title>
<desc id="d">AirStack's counts as deployed, and weekly registry downloads against each tool's own {mt["params"]["base_weeks"]}-week level, {day(w[0])} to {day(w[1])}. https://airstack.bot</desc>
<style>
:root{{--bg:#0A0A0B;--s1:#141416;--ink:#F5F5F7;--ink2:rgba(245,245,247,.62);--hair:rgba(255,255,255,.1);--up:#3DDC97;--dn:#FF6B5E;--acc:#FF4F00}}
@media (prefers-color-scheme:light){{:root{{--bg:#FFFFFF;--s1:#F5F5F7;--ink:#0A0A0B;--ink2:rgba(10,10,11,.6);--hair:rgba(0,0,0,.1);--up:#0A8F5A;--dn:#D33A2C}}}}
text{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Helvetica,Arial,sans-serif;fill:var(--ink)}}
.brand{{font-size:22px;font-weight:700;letter-spacing:-.02em}}.sub,.lab,.foot{{fill:var(--ink2)}}.sub{{font-size:15px}}.lab{{font-size:15px}}.foot{{font-size:13px}}
.big{{font-size:46px;font-weight:650;letter-spacing:-.03em;font-variant-numeric:tabular-nums}}
.tk{{font-size:15px;font-variant-numeric:tabular-nums}}.nm{{font-weight:600}}.up{{fill:var(--up)}}.dn{{fill:var(--dn)}}
.dot{{fill:var(--acc)}}.ring{{fill:none;stroke:var(--acc);stroke-width:2;transform-origin:56px 47px}}
.run{{animation:run {len(rows) * 4}s linear infinite}}
@keyframes run{{to{{transform:translateX(-{span}px)}}}}
@keyframes ping{{0%{{opacity:.7;transform:scale(1)}}80%,100%{{opacity:0;transform:scale(2.6)}}}}.ring{{animation:ping 2.4s cubic-bezier(0,0,.2,1) infinite}}
@media (prefers-reduced-motion:reduce){{.run,.ring{{animation:none}}.ring{{opacity:0}}}}
</style>
<rect width="1200" height="300" rx="20" fill="var(--bg)"/><rect x=".5" y=".5" width="1199" height="299" rx="19.5" fill="none" stroke="var(--hair)"/>
<circle class="ring" cx="56" cy="47" r="7"/><circle class="dot" cx="56" cy="47" r="7"/>
<text class="brand" x="74" y="55">AirStack</text><text class="sub" x="176" y="55">See the software market move · every claim linked to its source</text>
<text class="foot" x="1152" y="55" text-anchor="end">updated {day(mt["generated"])} · airstack.bot</text>
{cols}
<rect x="24" y="214" width="1152" height="62" rx="12" fill="var(--s1)"/>
<text class="foot" x="48" y="238">7-day downloads vs each tool's {mt["params"]["base_weeks"]}-week level · {day(w[0])} – {day(w[1])}</text>
<clipPath id="c"><rect x="40" y="244" width="1120" height="28"/></clipPath>
<g clip-path="url(#c)"><g transform="translate(48,262)"><g class="run">{strip}<g transform="translate({span},0)">{strip}</g></g></g></g>
</svg>
"""
    paths.STATS_SVG.write_text(svg)
    print(f"stats.svg: {', '.join(f'{n(v)} {ln}' for v, ln in tiles)}; {len(rows)} movers ({day(w[0])} to {day(w[1])})")

if __name__ == "__main__":
    main()
