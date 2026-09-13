#!/usr/bin/env bash
# Dumps the ITAP database to a timestamped, compressed custom-format
# file (`pg_restore`-only, not plain SQL — smaller, and restorable
# selectively) and prunes backups older than PG_BACKUP_RETENTION_DAYS.
# Meant to run as a scheduled CML Job (e.g. nightly) — this script has
# no scheduler of its own.
#
# Env vars: PG_DATA_DIR/PG_PORT/PG_USER/PG_DB as start.sh, plus:
#   PGPASSWORD                 - required (pg_dump reads it directly)
#   PG_BACKUP_DIR               - where dumps are written; must be
#                                 persistent storage, and ideally NOT
#                                 the same physical volume as
#                                 PG_DATA_DIR — a backup that lives on
#                                 the same disk as the thing it backs
#                                 up doesn't survive that disk failing.
#   PG_BACKUP_RETENTION_DAYS   - default 14.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-itap}"
PG_DB="${PG_DB:-itap}"
PG_BACKUP_DIR="${PG_BACKUP_DIR:?Set PG_BACKUP_DIR}"
RETENTION_DAYS="${PG_BACKUP_RETENTION_DAYS:-14}"
if [ -z "${PG_BIN_DIR:-}" ] && [ -d "$HERE/pg_bundle/bin" ]; then
  PG_BIN_DIR="$HERE/pg_bundle/bin"
fi
BIN="${PG_BIN_DIR:+$PG_BIN_DIR/}"
: "${PGPASSWORD:?Set PGPASSWORD}"

mkdir -p "$PG_BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="$PG_BACKUP_DIR/itap_${STAMP}.dump"

echo "Backing up $PG_DB to $OUT_FILE ..."
"${BIN}pg_dump" -h 127.0.0.1 -p "$PG_PORT" -U "$PG_USER" -Fc -f "$OUT_FILE" "$PG_DB"

SIZE=$(du -h "$OUT_FILE" | cut -f1)
echo "Backup complete: $OUT_FILE ($SIZE)"

echo "Pruning backups older than $RETENTION_DAYS days ..."
find "$PG_BACKUP_DIR" -maxdepth 1 -name 'itap_*.dump' -mtime "+$RETENTION_DAYS" -print -delete

echo "Backups currently on hand:"
ls -lh "$PG_BACKUP_DIR"/itap_*.dump 2>/dev/null || echo "(none)"
