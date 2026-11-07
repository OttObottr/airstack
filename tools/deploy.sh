#!/usr/bin/env bash
# spec: AS-131 AS-140 AS-202 AS-248 AS-252 AS-254 AS-256
# Deploy the tested commit as static assets with a pinned Wrangler bundle.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -n "$(git status --porcelain)" ]; then
  echo "deploy requires a clean working tree" >&2
  exit 1
fi
tools/assemble.sh public
printf '{"commit": "%s"}\n' "$(git rev-parse HEAD)" > public/version.json
echo "Deploying $(git rev-parse --short HEAD): $(ls public | tr '\n' ' ')"
WRANGLER_VERSION=4.156.0
WRANGLER_SHA256=934d8051582ed5d85336e9e6677126ec87324a47166974de22d49a5523ba4d11
: "${AIRSTACK_WRANGLER_JS:?set AIRSTACK_WRANGLER_JS to the reviewed Wrangler $WRANGLER_VERSION wrangler-dist/cli.js}"
[ -f "$AIRSTACK_WRANGLER_JS" ] || { echo "Wrangler bundle not found" >&2; exit 1; }
if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$AIRSTACK_WRANGLER_JS" | cut -d' ' -f1)
else
  actual=$(shasum -a 256 "$AIRSTACK_WRANGLER_JS" | cut -d' ' -f1)
fi
[ "$actual" = "$WRANGLER_SHA256" ] || { echo "Wrangler bundle checksum mismatch" >&2; exit 1; }
installed=$(node "$AIRSTACK_WRANGLER_JS" --version 2>/dev/null | sed -nE 's/.*([0-9]+\.[0-9]+\.[0-9]+).*/\1/p' | head -1)
[ "$installed" = "$WRANGLER_VERSION" ] || {
  echo "Wrangler $WRANGLER_VERSION is required; found ${installed:-an unreadable version}" >&2
  exit 1
}
node "$AIRSTACK_WRANGLER_JS" deploy "$@"
