#!/usr/bin/env bash
# Compile the site's utility CSS with the Tailwind standalone CLI, pinned by version and checksum; it runs at build time only.
# Usage: tools/tailwind.sh <output.css>
set -euo pipefail
cd "$(dirname "$0")/.."
version=v4.3.3
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) asset=tailwindcss-macos-arm64 sum=cdf646702987a743464dff4d9c60fd4480d1c1e73dd819a9a67f1078815dce9d ;;
  Linux-x86_64) asset=tailwindcss-linux-x64 sum=dc61b3ac6b8c9ca874c0cc4c57b2409791a64c5540404ca5f5367360babc313a ;;
  *) echo "no pinned Tailwind binary for $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac
bin="${XDG_CACHE_HOME:-$HOME/.cache}/airstack/$asset-$version"
if [ ! -x "$bin" ] || ! echo "$sum  $bin" | shasum -a 256 -c - >/dev/null 2>&1; then
  mkdir -p "$(dirname "$bin")"
  curl -fsSL --proto '=https' -o "$bin.part" "https://github.com/tailwindlabs/tailwindcss/releases/download/$version/$asset"
  echo "$sum  $bin.part" | shasum -a 256 -c - >/dev/null || { rm -f "$bin.part"; echo "Tailwind checksum mismatch" >&2; exit 1; }
  chmod +x "$bin.part" && mv "$bin.part" "$bin"
fi
"$bin" -i web/src/styles/app.css -o "${1:?usage: tools/tailwind.sh <output.css>}" --minify
