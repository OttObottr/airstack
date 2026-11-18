#!/usr/bin/env bash
# Download the files the MCP server reads into data/site, each checked against the published manifest. The previous copy is
# replaced only when every file has arrived and matches.
# Usage: ./pull.sh [base-url]    (default https://airstack.bot)
set -euo pipefail
cd "$(dirname "$0")"
base="${1:-https://airstack.bot}"
mkdir -p data
stage=$(mktemp -d data/.pull.XXXXXX)
trap 'rm -rf "$stage"' EXIT
for name in data-manifest.json site-data.js profiles.json chain-data.json; do
  curl -fsSL --proto =https --max-redirs 2 --compressed --max-time 120 --max-filesize 24000000 -A airstack-data/1 "$base/$name" -o "$stage/$name"
done
python3 - "$stage" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1]); m = json.loads((root / "data-manifest.json").read_text())
bad = [n for n in ("site-data.js", "profiles.json", "chain-data.json") if hashlib.sha256((root / n).read_bytes()).hexdigest() != m.get(n)]
sys.exit(f"not as published: {', '.join(bad)}" if bad else 0)
PY
rm -rf data/site.old; [ ! -d data/site ] || mv data/site data/site.old
mv "$stage" data/site; trap - EXIT; rm -rf data/site.old
echo "data/site: the published files, checked"
