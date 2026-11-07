#!/usr/bin/env bash
# spec: AS-365
# A dated archive of everything that is not in the repository: the saved responses, the intermediate files and the databases (including the paid
# corpus), plus the published datasets. This is the only copy of the paid database apart from this machine's own disk: keep the archives
# somewhere other than this disk (an external drive, another machine). It deletes nothing.
# Restore: tar -xzf <archive> -C "${AIRSTACK_DATA:-data}"
# Usage: tools/backup.sh [destination folder]    default: $AIRSTACK_BACKUPS or ~/airstack-backups
set -euo pipefail
cd "$(dirname "$0")/.."
data="${AIRSTACK_DATA:-data}"; dest="${1:-${AIRSTACK_BACKUPS:-$HOME/airstack-backups}}"; mkdir -p "$dest"
file="$dest/airstack-data-$(date +%F).tar.gz"
tar -czf "$file" -C "$data" .
listed="$(tar -tzf "$file" | wc -l | tr -d ' ')"
(cd "$dest" && shasum -a 256 "$(basename "$file")" > "$(basename "$file").sha256")
echo "backed up $listed entries ($(du -h "$file" | cut -f1)) to $file"
