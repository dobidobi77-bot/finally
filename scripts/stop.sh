#!/usr/bin/env bash
# Stop FinAlly. Idempotent. Never removes the database.
# Usage: scripts/stop.sh
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# 'down' without -v leaves the finally-data volume untouched.
compose down

echo "FinAlly stopped. The finally-data volume is untouched."
