#!/usr/bin/env bash
# Assemble the site as it ships: web/ with its stylesheets inlined, web/public/, the allowlisted datasets and the rendered pages.
# Usage: tools/assemble.sh <dir>
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/backend:$PWD/backend/tools:$PWD/tools${PYTHONPATH:+:$PYTHONPATH}"
out="${1:?usage: tools/assemble.sh <dir>}"
py=.venv/bin/python; [ -x "$py" ] || py=python3
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
list=$(mktemp); trap 'rm -f "$list"' EXIT
"$py" - "$site" > "$list" <<'PY'
import json, pathlib, re, sys
from validate_published_data import MAX_FILES, MAX_TOTAL_BYTES, parse_data

site = pathlib.Path(sys.argv[1])
allowed = set(json.loads(pathlib.Path("config/published-files.json").read_text())["files"])
monthly = re.compile(r"open-data/airstack-\d{4}-\d{2}\.jsonl\.gz")
shipped, total = [], 0
for path in sorted(site.rglob("*")):
    name = path.relative_to(site).as_posix()
    if path.is_symlink():
        raise SystemExit(f"refusing published dataset symlink: {name}")
    if path.is_file() and (name in allowed or monthly.fullmatch(name)):
        shipped.append(name)
        total += len(parse_data(path))
missing = sorted(allowed - set(shipped))
if missing:
    raise SystemExit(f"published datasets missing: {', '.join(missing)}")
if len(shipped) > MAX_FILES or total > MAX_TOTAL_BYTES:
    raise SystemExit(f"published datasets exceed {MAX_FILES} files or {MAX_TOTAL_BYTES} bytes")
print("\n".join(shipped))
PY
"$py" backend/tools/build_pages.py >/dev/null
rm -rf "$out" && mkdir -p "$out"
cp -R web/public/. "$out"/
cp -R c compare p o t insights calendar method "$out"/
"$py" - "$out" "$site" "$list" <<'PY'
import hashlib, json, pathlib, re, shutil, sys
out, web, site = pathlib.Path(sys.argv[1]), pathlib.Path("web"), pathlib.Path(sys.argv[2])
shipped = pathlib.Path(sys.argv[3]).read_text().split()
for name in shipped:
    (out / name).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(site / name, out / name)
page = (web / "index.html").read_text()
index = (web / "src" / "styles" / "index.css").read_text()
plain = lambda css: "\n".join(l.strip() for l in re.sub(r"/\*[\s\S]*?\*/", "", css).splitlines() if l.strip())
css = [plain(s) for s in re.findall(r"(?m)^@layer [\w, -]+;", index)]
for name, layer in re.findall(r'(?m)^@import "\./([\w.-]+\.css)"(?: layer\(([\w-]+)\))?;', index):
    body = plain((web / "src" / "styles" / name).read_text())
    css.append(f"@layer {layer}{{\n{body}\n}}" if layer else body)
link = '<link rel="stylesheet" href="src/styles/index.css">'
assert page.count(link) == 1 and "<script>" not in page, "the shell links index.css once and carries no inline script"
for m in sorted(p.relative_to(web).as_posix() for p in (web / "src").rglob("*.js")):
    (out / m).parent.mkdir(parents=True, exist_ok=True); (out / m).write_bytes((web / m).read_bytes())
preload = '<link rel="modulepreload" href="src/main.js">'
# First-screen text from the data, as components/hero.js writes it, so nothing moves when the modules run.
data = (site / "site-data.js").read_text(); sd = json.loads(data[data.index("{"):data.rindex("}") + 1])
y, mo, d = re.match(r"(\d{4})-(\d{2})-(\d{2})", sd["meta"]["checked_at"]).groups()
fd = f"{int(d)} {'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[int(mo) - 1]} {y}"
was = '<p class="honest" id="honest">Every fact quoted from its own page</p>'
assert page.count(was) == 1, f"the shell no longer holds {was}"
page = page.replace(was, f'<p class="honest" id="honest">Scope: {sd["dir"]["researched"]:,} researched products · every fact quoted from its own page\nAs of {fd}</p>')
page, away = re.subn(r'<section class="([^"]*)"( id="[\w-]+" data-views="([^"]+)")',
                     lambda m: m[0] if "overview" in m[3].split() else f'<section class="{m[1]} view-away"{m[2]}', page)
tab = '<a href="#/" data-view="overview">'
assert away >= 10 and page.count(tab) == 1, "the shell's views and tabs are not where assembly expects them"
page = page.replace(tab, tab[:-1] + ' aria-current="page">')
(out / "index.html").write_text(page.replace(link, "<style>" + "\n".join(css) + "</style>\n" + preload))
(out / "data-manifest.json").write_text(json.dumps({f: hashlib.sha256((out / f).read_bytes()).hexdigest() for f in shipped}, indent=1) + "\n")
PY
