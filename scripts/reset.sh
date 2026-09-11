#!/usr/bin/env bash
# Reset FinAlly to a fresh state: stop the app, DELETE the finally-data volume
# (portfolio, trades, chat history - everything), start again and wait until
# /api/health reports cache_ready. Unrecoverable.
#
# Usage: scripts/reset.sh [--yes] [--test]
#   --yes   skip the confirmation prompt
#   --test  restart with docker-compose.test.yml layered in (simulator + mock LLM)
#
# The database lives in the named volume, not under ./db, so the volume must go.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

YES=0
TEST=0
for arg in "$@"; do
  case "$arg" in
    --yes) YES=1 ;;
    --test) TEST=1 ;;
    *) echo "Unknown argument: $arg" >&2; echo "Usage: scripts/reset.sh [--yes] [--test]" >&2; exit 1 ;;
  esac
done

FILES="docker-compose.yml"
if [ "$TEST" -eq 1 ]; then
  FILES="$TEST_FILES"
fi

if [ "$YES" -ne 1 ]; then
  echo "This will stop FinAlly and delete the finally-data volume:"
  echo "  cash balance, positions, trade history, watchlist and chat history."
  echo "This cannot be undone."
  read -r -p "Type 'yes' to continue: " answer
  if [ "$answer" != "yes" ]; then
    echo "Aborted. Nothing was changed."
    exit 1
  fi
fi

ensure_env

echo "Stopping FinAlly and removing the finally-data volume..."
compose_with "$FILES" down -v

if [ "$TEST" -eq 1 ]; then
  echo "Starting FinAlly in test mode (simulator, mock LLM)..."
else
  echo "Starting FinAlly..."
fi
compose_with "$FILES" up -d

wait_for_health 120

echo ""
echo "FinAlly has been reset and is running at $APP_URL"
