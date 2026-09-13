#!/usr/bin/env bash
# Exit 0 if Postgres is accepting connections and has headroom on its
# data volume, non-zero otherwise. Meant to be run:
#   - from a scheduled CML Job, alerting (however your CML setup
#     notifies on job failure) on a non-zero exit
#   - manually, as the first step of the downtime runbook in README.md,
#     to confirm the service actually came back up after maintenance
#
# Env vars: same PG_DATA_DIR / PG_PORT / PG_USER as start.sh.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PG_DATA_DIR="${PG_DATA_DIR:?Set PG_DATA_DIR}"
PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-itap}"
if [ -z "${PG_BIN_DIR:-}" ] && [ -d "$HERE/pg_bundle/bin" ]; then
  PG_BIN_DIR="$HERE/pg_bundle/bin"
fi
BIN="${PG_BIN_DIR:+$PG_BIN_DIR/}"
DISK_WARN_PERCENT="${DISK_WARN_PERCENT:-85}"

if ! "${BIN}pg_isready" -p "$PG_PORT" -U "$PG_USER" -q; then
  echo "FAIL: Postgres is not accepting connections on port $PG_PORT"
  exit 1
fi

USED_PERCENT=$(df -P "$PG_DATA_DIR" | awk 'NR==2 {gsub("%","",$5); print $5}')
if [ -n "$USED_PERCENT" ] && [ "$USED_PERCENT" -ge "$DISK_WARN_PERCENT" ]; then
  echo "WARN: data volume at ${USED_PERCENT}% (threshold ${DISK_WARN_PERCENT}%) — $PG_DATA_DIR"
  exit 2
fi

echo "OK: Postgres accepting connections on port $PG_PORT, data volume at ${USED_PERCENT:-unknown}%"
exit 0
