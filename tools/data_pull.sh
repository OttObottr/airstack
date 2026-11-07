#!/usr/bin/env bash
# spec: AS-365
# Data is not in the repository (and never on GitHub). Production serves every published dataset beside a manifest of checksums; this downloads
# them into $AIRSTACK_DATA/site (default data/site) and verifies each one, so the code can be built, tested and deployed from a fresh clone, and
# so production can be copied back to this machine. The saved responses and the paid databases are never published: tools/backup.sh keeps them.
# The manifest is untrusted until every path, type, size, payload and checksum passes tools/validate_published_data.py.
# Downloads land in a temporary sibling and replace data/site only after the complete snapshot validates.
# Usage: tools/data_pull.sh [base-url]     default https://airstack.bot
set -euo pipefail
cd "$(dirname "$0")/.."
base="${1:-https://airstack.bot}"; data_root="${AIRSTACK_DATA:-data}"; site="$data_root/site"
mkdir -p "$data_root"
stage=$(mktemp -d "$data_root/.site-pull.XXXXXX")
trap 'rm -rf "$stage"' EXIT
curl -fsS --compressed --max-time 60 --max-filesize 131072 "$base/data-manifest.json" -o "$stage/data-manifest.json"
expected="${AIRSTACK_MANIFEST_SHA256:-$(tr -d '[:space:]' < config/published-data.sha256)}"
if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$stage/data-manifest.json" | cut -d' ' -f1)
else
  actual=$(shasum -a 256 "$stage/data-manifest.json" | cut -d' ' -f1)
fi
[ "$actual" = "$expected" ] || { echo "refused published data: manifest is not the reviewed release" >&2; exit 1; }
python3 - "$stage/data-manifest.json" <<'PY' > "$stage/files.txt"
import json, pathlib, re, sys
p = pathlib.Path(sys.argv[1]); manifest = json.loads(p.read_text())
if not isinstance(manifest, dict) or not 1 <= len(manifest) <= 128:
    raise SystemExit("refused published data: invalid manifest size")
for name, digest in manifest.items():
    q = pathlib.PurePosixPath(name)
    if not isinstance(name, str) or name != q.as_posix() or q.is_absolute() or not 1 <= len(q.parts) <= 4 or any(x in ("", ".", "..") or x.startswith(".") for x in q.parts):
        raise SystemExit(f"refused published data: unsafe path {name!r}")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise SystemExit(f"refused published data: bad checksum for {name!r}")
    print(name)
PY
total=0
while IFS= read -r name; do
  mkdir -p "$(dirname "$stage/$name")"
  curl -fsS --compressed --max-time 120 --max-filesize 20000000 "$base/$name" -o "$stage/$name"
  size=$(wc -c < "$stage/$name" | tr -d ' ')
  [ "$size" -le 20000000 ] || { echo "refused published data: $name exceeds 20000000 bytes" >&2; exit 1; }
  total=$((total + size))
  [ "$total" -le 64000000 ] || { echo "refused published data: snapshot exceeds 64000000 bytes" >&2; exit 1; }
done < "$stage/files.txt"
rm "$stage/files.txt"
python3 tools/validate_published_data.py "$stage"
old="$data_root/.site-previous"
rm -rf "$old"
if [ -d "$site" ]; then mv "$site" "$old"; fi
mv "$stage" "$site"
stage="$data_root/.site-pull.replaced"
rm -rf "$old"
echo "datasets in $site: $(find "$site" -type f | wc -l | tr -d ' ') entries"
