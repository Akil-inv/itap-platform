#!/usr/bin/env bash
# Restores a backup.sh dump into a FRESH, empty database — never onto
# an existing one (pg_restore --clean --create against a live DB with
# other connections is exactly how you corrupt a restore halfway
# through). Practice this before you ever need it for real: run it
# against a throwaway DB name and diff row counts against the source.
#
# Usage: PG_BACKUP_FILE=/path/to/itap_20260101T000000Z.dump bash restore.sh
#
# Env vars: PG_PORT/PG_USER as start.sh, plus:
#   PG_BACKUP_FILE   - the .dump file to restore (required)
#   PG_RESTORE_DB    - database name to restore INTO (default
#                      "itap_restore" — deliberately not "itap" itself,
#                      so a bad restore never touches the live database;
#                      swap the app's DATABASE_URL over to it yourself
#                      once you've verified it, per the downtime runbook
#                      in README.md)
#   PGPASSWORD       - required
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-itap}"
PG_BACKUP_FILE="${PG_BACKUP_FILE:?Set PG_BACKUP_FILE to the .dump file to restore}"
PG_RESTORE_DB="${PG_RESTORE_DB:-itap_restore}"
if [ -z "${PG_BIN_DIR:-}" ] && [ -d "$HERE/pg_bundle/bin" ]; then
  PG_BIN_DIR="$HERE/pg_bundle/bin"
fi
BIN="${PG_BIN_DIR:+$PG_BIN_DIR/}"
: "${PGPASSWORD:?Set PGPASSWORD}"

if [ ! -f "$PG_BACKUP_FILE" ]; then
  echo "No such backup file: $PG_BACKUP_FILE" >&2
  exit 1
fi

echo "Creating fresh database '$PG_RESTORE_DB' ..."
"${BIN}dropdb" -h 127.0.0.1 -p "$PG_PORT" -U "$PG_USER" --if-exists "$PG_RESTORE_DB"
"${BIN}createdb" -h 127.0.0.1 -p "$PG_PORT" -U "$PG_USER" "$PG_RESTORE_DB"

echo "Restoring $PG_BACKUP_FILE into $PG_RESTORE_DB ..."
"${BIN}pg_restore" -h 127.0.0.1 -p "$PG_PORT" -U "$PG_USER" -d "$PG_RESTORE_DB" "$PG_BACKUP_FILE"

echo "Done. Verify before cutting over:"
echo "  psql -h 127.0.0.1 -p $PG_PORT -U $PG_USER -d $PG_RESTORE_DB -c \"select count(*) from parties;\""
