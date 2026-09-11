#!/usr/bin/env bash
# Shared helpers for scripts/*.sh. Source it; do not run it directly.
#
#   source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
#
# Sets ROOT, cds into it, and defines:
#   compose ARGS...           run docker compose (plugin or standalone)
#   compose_with FILES ARGS   same, with explicit -f files (FILES is space separated)
#   ensure_env               create .env from .env.example when missing
#   wait_for_health SECONDS  poll /api/health until cache_ready is true

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

APP_URL="http://localhost:8000"
TEST_FILES="docker-compose.yml docker-compose.test.yml"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed or not on PATH." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "ERROR: neither 'docker compose' nor 'docker-compose' is available." >&2
  exit 1
fi

compose() {
  "${COMPOSE[@]}" "$@"
}

compose_with() {
  local files="$1"; shift
  local args=()
  local f
  for f in $files; do
    args+=(-f "$f")
  done
  "${COMPOSE[@]}" "${args[@]}" "$@"
}

ensure_env() {
  if [ ! -f .env ]; then
    echo "No .env found - creating one from .env.example."
    echo "Edit .env and add your OPENROUTER_API_KEY to enable the AI chat."
    cp .env.example .env
  fi
}

# Returns 0 once /api/health reports cache_ready: true, 1 on timeout.
wait_for_health() {
  local timeout="${1:-120}"
  local deadline=$(( $(date +%s) + timeout ))
  local body
  echo "Waiting for $APP_URL/api/health (up to ${timeout}s)..."
  while [ "$(date +%s)" -lt "$deadline" ]; do
    body="$(curl -fsS --max-time 5 "$APP_URL/api/health" 2>/dev/null || true)"
    if printf '%s' "$body" | grep -Eq '"cache_ready": *true'; then
      echo "Healthy: $body"
      return 0
    fi
    sleep 1
  done
  echo "ERROR: app not healthy after ${timeout}s. Last response: ${body:-<none>}" >&2
  echo "Logs: ${COMPOSE[*]} logs" >&2
  return 1
}
