#!/usr/bin/env bash
# spec: AS-100 AS-120 AS-131 AS-256 AS-258 AS-259 AS-280 AS-285 AS-316 AS-317 AS-318 AS-319 AS-365
# Assembles the site exactly as it ships into the directory given: the page from web/ (its stylesheets inlined in <head>, its ES modules
# served as they are under src/, each named by a modulepreload link), the static assets from web/public/, the published datasets beside it (read from $AIRSTACK_DATA/site,
# default data/site: not in the repository, see tools/data_pull.sh), fonts and icons, the pages rendered from those datasets, and
# data-manifest.json (a checksum for each dataset). deploy.sh ships it, the journeys serve it, and verify_deploy.py compares production with it.
# Nothing here installs a package, regenerates data or calls a model.
# Usage: tools/assemble.sh <dir>
set -euo pipefail
cd "$(dirname "$0")/.."
out="${1:?usage: tools/assemble.sh <dir>}"
py=.venv/bin/python; [ -x "$py" ] || py=python3                       # CI has no virtualenv: its Python has the requirements installed
# The only destructive step removes this directory. Accept the release target and isolated test temp directories, never a broad or redirected path.
out=$("$py" - "$out" <<'PY'
import pathlib, sys, tempfile

raw = pathlib.Path(sys.argv[1])
if ".." in raw.parts:
    raise SystemExit("refusing unsafe assembly output: parent traversal")
repo, home = pathlib.Path.cwd().resolve(), pathlib.Path.home().resolve()
temp = pathlib.Path(tempfile.gettempdir()).resolve()
candidate = raw if raw.is_absolute() else pathlib.Path.cwd() / raw
cursor = pathlib.Path(candidate.anchor)
system_ancestors = {repo, temp, *repo.parents, *temp.parents}
for part in candidate.parts[1:]:
    cursor /= part
    if cursor.is_symlink() and cursor.resolve() not in system_ancestors:
        raise SystemExit(f"refusing unsafe assembly output: symlinked path {cursor}")
target = candidate.resolve(strict=False)
if target in {pathlib.Path(target.anchor), repo, home, temp}:
    raise SystemExit(f"refusing unsafe assembly output: {target}")
if target != repo / "public" and temp not in target.parents:
    raise SystemExit(f"refusing assembly output outside public or a test temp directory: {target}")
print(target)
PY
)
site="${AIRSTACK_DATA:-data}/site"
[ -f "$site/site-data.js" ] || { echo "no datasets in $site: run tools/data_pull.sh" >&2; exit 1; }
# data/site is ignored by git, so validate its complete shape before any builder reads it or any byte is copied to the release tree.
"$py" - "$site" <<'PY'
import json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path("tools").resolve()))
from validate_published_data import MAX_FILES, MAX_TOTAL_BYTES, parse_data

site = pathlib.Path(sys.argv[1])
policy = json.loads(pathlib.Path("config/published-files.json").read_text())
allowed = set(policy["files"])
monthly = re.compile(r"open-data/airstack-\d{4}-\d{2}\.jsonl\.gz")
seen, total = set(), 0
for path in site.rglob("*"):
    name = path.relative_to(site).as_posix()
    if path.is_symlink():
        raise SystemExit(f"refusing published dataset symlink: {name}")
    if path.is_dir():
        continue
    if not path.is_file():
        raise SystemExit(f"refusing non-regular published dataset: {name}")
    if name == "data-manifest.json":
        json.loads(path.read_text())
        continue
    if name not in allowed and not monthly.fullmatch(name):
        raise SystemExit(f"refusing unapproved published dataset: {name}")
    seen.add(name)
    if len(seen) > MAX_FILES:
        raise SystemExit(f"refusing more than {MAX_FILES} published datasets")
    total += len(parse_data(path))
missing = sorted(allowed - seen)
if missing:
    raise SystemExit(f"published datasets missing: {', '.join(missing)}")
if total > MAX_TOTAL_BYTES:
    raise SystemExit(f"published datasets exceed {MAX_TOTAL_BYTES} bytes")
PY
"$py" backend/tools/build_pages.py >/dev/null
rm -rf "$out" && mkdir -p "$out"
cp -R web/public/. "$out"/                                             # the static assets: _headers, 404.html, sw.js, manifest, robots, llms.txt, fonts, icons, legal
cp config/category-guides.json "$out"/
cp -R "$site"/. "$out"/ && rm -f "$out/data-manifest.json"                  # data/site is, by definition, everything that is published
cp -R c compare p o t "$out"/
# The page: the stylesheets in index.css's order and layers, inlined, so first paint needs no second request; the modules copied as files.
# The CSP allows scripts from this origin only ('self'): no inline script runs, so an injected one cannot.
"$py" - "$out" "$site" <<'PY'
import hashlib, json, pathlib, re, sys
out, web, site = pathlib.Path(sys.argv[1]), pathlib.Path("web"), pathlib.Path(sys.argv[2])
page = (web / "index.html").read_text()
index = (web / "src" / "styles" / "index.css").read_text()
plain = lambda css: "\n".join(l.strip() for l in re.sub(r"/\*[\s\S]*?\*/", "", css).splitlines() if l.strip())
css = [plain(s) for s in re.findall(r"(?m)^@layer [\w, -]+;", index)]
for name, layer in re.findall(r'(?m)^@import "\./([\w.-]+\.css)"(?: layer\(([\w-]+)\))?;', index):
    body = plain((web / "src" / "styles" / name).read_text())
    css.append(f"@layer {layer}{{\n{body}\n}}" if layer else body)
link = '<link rel="stylesheet" href="src/styles/index.css">'
assert page.count(link) == 1 and "<script>" not in page, "the shell links index.css once and carries no inline script"
modules = sorted(p.relative_to(web).as_posix() for p in (web / "src").rglob("*.js"))
for m in modules:
    (out / m).parent.mkdir(parents=True, exist_ok=True); (out / m).write_bytes((web / m).read_bytes())
lazy = set(re.findall(r"import\('\./([\w.-]+\.js)'\)", "".join((web / m).read_text() for m in modules)))   # loaded on first use (palette, compare): cached by the service worker, not fetched at start-up
preload = "\n".join(f'<link rel="modulepreload" href="{m}">' for m in ["src/main.js"] + [m for m in modules if m != "src/main.js" and m.rsplit("/", 1)[-1] not in lazy])
# the first screen's text that comes from the data, written as components/hero.js writes it, so nothing moves when the modules run
data = (site / "site-data.js").read_text(); sd = json.loads(data[data.index("{"):data.rindex("}") + 1]); meta = sd["meta"]
y, mo, d = re.match(r"(\d{4})-(\d{2})-(\d{2})", meta["checked_at"]).groups()
fd = f"{int(d)} {'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[int(mo) - 1]} {y}"
first = {'<p class="honest" id="honest">Every fact quoted from its own page</p>':
           f'<p class="honest" id="honest">Scope: {sd["dir"]["researched"]:,} researched products · every fact quoted from its own page\nAs of {fd} · {"researched with Muse Spark" if meta["live"] else "verified from stored evidence"}</p>',
         '<span id="built">Built for Muse Spark</span>': f'<span id="built">Built {"with" if meta["live"] else "for"} Muse Spark</span>'}
for was, now in first.items():
    assert page.count(was) == 1, f"the shell no longer holds {was}"
    page = page.replace(was, now)
# and the default view (Overview) as lib/router.js leaves it, so the first layout holds only what Overview shows
page, away = re.subn(r'<section class="([^"]*)"( id="[\w-]+" data-views="([^"]+)")',
                     lambda m: m[0] if "overview" in m[3].split() else f'<section class="{m[1]} view-away"{m[2]}', page)
tab = '<a href="#/" data-view="overview">'
assert away >= 10 and page.count(tab) == 1, "the shell's views and tabs are not where assembly expects them"
page = page.replace(tab, tab[:-1] + ' aria-current="page">')
(out / "index.html").write_text(page.replace(link, "<style>" + "\n".join(css) + "</style>\n" + preload))
sw = (out / "sw.js").read_text()
assert sw.count("const MODULES = [];") == 1, "sw.js names the modules it precaches exactly once"
(out / "sw.js").write_text(sw.replace("const MODULES = [];", "const MODULES = " + json.dumps(modules) + ";"))
shipped = sorted(p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file() and p.name != "data-manifest.json")
policy = json.loads(pathlib.Path("config/published-files.json").read_text())
allowed = set(policy["files"])
monthly = re.compile(r"open-data/airstack-\d{4}-\d{2}\.jsonl\.gz")
unexpected = [name for name in shipped if name not in allowed and not monthly.fullmatch(name)]
missing = sorted(name for name in allowed if name not in shipped)
assert not unexpected and not missing, f"published dataset policy mismatch: unexpected={unexpected}, missing={missing}"
(out / "data-manifest.json").write_text(json.dumps({f: hashlib.sha256((out / f).read_bytes()).hexdigest() for f in shipped}, indent=1) + "\n")
PY
