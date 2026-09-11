#!/usr/bin/env bash
# Restart FinAlly WITHOUT touching the database, and wait until /api/health
# reports cache_ready. The opposite of reset.sh.
#
# Usage: scripts/restart.sh [--yes] [--test]
#   --yes   accepted for symmetry with reset.sh; there is nothing to confirm
#   --test  restart with docker-compose.test.yml layered in (simulator + mock LLM)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

TEST=0
for arg in "$@"; do
  case "$arg" in
    --yes) ;;
    --test) TEST=1 ;;
    *) echo "Unknown argument: $arg" >&2; echo "Usage: scripts/restart.sh [--yes] [--test]" >&2; exit 1 ;;
  esac
done

FILES="docker-compose.yml"
if [ "$TEST" -eq 1 ]; then
  FILES="$TEST_FILES"
fi

ensure_env

# 'down' without -v leaves the finally-data volume untouched.
echo "Stopping FinAlly (data is kept)..."
compose_with "$FILES" down

if [ "$TEST" -eq 1 ]; then
  echo "Starting FinAlly in test mode (simulator, mock LLM)..."
else
  echo "Starting FinAlly..."
fi
compose_with "$FILES" up -d

wait_for_health 120

echo ""
echo "FinAlly restarted at $APP_URL"
