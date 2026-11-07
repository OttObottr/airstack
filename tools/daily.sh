#!/usr/bin/env bash
# spec: AS-263 AS-274 AS-351 AS-365
# The daily refresh, run by launchd at 06:00 (tools/bot.airstack.daily.plist; install with tools/daily.sh --install).
# 1. Free: registry movers, vendor news and conditional re-checks of pages due today.
# 2. Rebuild generated files and run the local verification suite.
# 3. Stop. A scheduled job never pulls or executes new repository code, authorizes paid work, commits, pushes or deploys.
#    Lost quotes are written to data/rechecks/lost-a-quote.txt for a person to review and, when appropriate, re-extract with
#    an explicitly supplied account cap. Publication is always a separate, manual release.
# Skips, and says so, when the checkout has uncommitted work (a session is mid-change). Logs: ~/.airstack/daily/<date>.log
set -uo pipefail
cd "$(dirname "$0")/.."
if [ "${1:-}" = "--install" ]; then
  sed "s|__REPO__|$(pwd)|g; s|__HOME__|$HOME|g" tools/bot.airstack.daily.plist > "$HOME/Library/LaunchAgents/bot.airstack.daily.plist"
  launchctl bootout "gui/$(id -u)/bot.airstack.daily" 2>/dev/null; launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/bot.airstack.daily.plist"
  echo "installed: runs daily at 06:00; logs in ~/.airstack/daily/"; exit 0
fi
LOG_DIR="$HOME/.airstack/daily"; mkdir -p "$LOG_DIR"; exec >>"$LOG_DIR/$(date +%F).log" 2>&1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export PYTHONPATH="$PWD/backend${PYTHONPATH:+:$PYTHONPATH}"
say() { echo "$(date '+%F %T') $*"; }
notify() { osascript -e "display notification \"$1\" with title \"AirStack daily\"" >/dev/null 2>&1 || true; }
fail() { say "STOPPED: $1"; notify "Stopped: $1"; exit 1; }
PY=.venv/bin/python
say "start"
[ -z "$(git status --porcelain)" ] || { say "skipped: uncommitted work in the checkout"; notify "Skipped: uncommitted work in the checkout"; exit 0; }
$PY backend/tools/build_movers.py || fail "movers"
$PY backend/tools/build_news.py --fetch || fail "news"
(cd backend && ../$PY -m airstack.fetch --sweep) || fail "robots sweep"
$PY backend/tools/refresh.py --check 3000 || fail "re-checks"
IDS=$(cat data/rechecks/lost-a-quote.txt 2>/dev/null || true)
if [ -n "$IDS" ]; then
  say "review required: one or more pages lost a quote; no paid re-extraction was attempted"
  notify "Review pages that lost a quote"
fi
for t in build_market_data build_site_data build_chain_data build_insights build_stats build_feed; do $PY backend/tools/$t.py >/dev/null || fail "$t"; done
$PY backend/tools/refresh.py --publish >/dev/null || fail "freshness"
$PY tools/update_counts.py >/dev/null || fail "counts"
$PY tools/spec_audit.py >/dev/null || fail "spec audit"
$PY -m pytest -q backend/tests JOURNEY -p no:cacheprovider -x || fail "tests failed: nothing committed or deployed"
if ! git diff --quiet -- README.md web/public/llms.txt config/numbers.json; then
  say "counts changed locally; review and release them manually"
fi
if [ "$(date +%u)" = 7 ]; then tools/backup.sh || say "backup failed"; fi
say "done: local data refreshed and verified; nothing was spent, pulled, committed, pushed or deployed"
notify "Local refresh verified; review before release"
