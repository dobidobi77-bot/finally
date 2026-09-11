#!/usr/bin/env bash
# Start FinAlly. Idempotent - safe to run repeatedly.
# Usage: scripts/start.sh [--build] [--open]
#   --build  rebuild the image before starting
#   --open   open http://localhost:8000 in the default browser once healthy
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

BUILD=0
OPEN=0
for arg in "$@"; do
  case "$arg" in
    --build) BUILD=1 ;;
    --open) OPEN=1 ;;
    *) echo "Unknown argument: $arg" >&2; echo "Usage: scripts/start.sh [--build] [--open]" >&2; exit 1 ;;
  esac
done

ensure_env

if [ "$BUILD" -eq 1 ]; then
  compose up -d --build
else
  compose up -d
fi

echo ""
echo "FinAlly is starting at $APP_URL"
echo "Logs:  ${COMPOSE[*]} logs -f"
echo "Stop:  scripts/stop.sh"
echo "Reset: scripts/reset.sh   (wipes the portfolio)"

if [ "$OPEN" -eq 1 ]; then
  wait_for_health 120
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$APP_URL" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$APP_URL" || true
  fi
fi
