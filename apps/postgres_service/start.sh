#!/usr/bin/env bash
# Starts (initializing on first run) a self-contained Postgres instance
# whose data directory lives on whatever persistent storage you point it
# at — no CML-managed database service required. Runs Postgres in the
# FOREGROUND (`postgres` directly, not `pg_ctl start` which daemonizes)
# so a process supervisor — a dedicated CML Application's own process,
# or the Streamlit app's subprocess wrapper (see pg_embedded.py) —
# can see it die and restart it, rather than losing track of a
# detached background process.
#
# Required env vars:
#   PG_DATA_DIR   - where to init/keep the data directory. MUST be on
#                   storage that survives an app restart/redeploy, or
#                   every restart starts from an empty database. In
#                   CML this is your project's persistent mount, not
#                   /tmp and not the container's own root filesystem
#                   unless you've confirmed that filesystem persists.
#   PG_PORT       - TCP port to listen on (default 5432).
#   PG_DB / PG_USER / PG_PASSWORD - bootstrapped on first run only.
#
# Optional:
#   PG_BIN_DIR    - directory containing initdb/postgres/psql, if not
#                   already on PATH. Defaults to ./pg_bundle/bin next
#                   to this script if that directory exists (the
#                   bundle build_postgres_bundle.sh produces) — see
#                   this directory's README for how that bundle is
#                   built and why it needs no matching system glibc.
#
# Usage: PG_DATA_DIR=/path/to/pgdata PG_PASSWORD=... bash start.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PG_DATA_DIR="${PG_DATA_DIR:?Set PG_DATA_DIR to a persistent path}"
PG_PORT="${PG_PORT:-5432}"
PG_DB="${PG_DB:-itap}"
PG_USER="${PG_USER:-itap}"
PG_PASSWORD="${PG_PASSWORD:?Set PG_PASSWORD}"

if [ -z "${PG_BIN_DIR:-}" ] && [ -d "$HERE/pg_bundle/bin" ]; then
  PG_BIN_DIR="$HERE/pg_bundle/bin"
fi
BIN="${PG_BIN_DIR:+$PG_BIN_DIR/}"

# The bundle's binaries ship with a placeholder ELF interpreter path
# (see pg_bundle/patch_interpreter.py) that has to be rewritten to
# wherever this bundle actually landed before any of them will run.
# Idempotent — a no-op once already patched — so this is safe on every
# start, not just the first.
if [ -n "${PG_BIN_DIR:-}" ] && [ -f "$HERE/patch_interpreter.py" ]; then
  python3 "$HERE/patch_interpreter.py"
fi

if [ ! -f "$PG_DATA_DIR/PG_VERSION" ]; then
  echo "No existing data directory at $PG_DATA_DIR — initializing..."
  mkdir -p "$PG_DATA_DIR"
  # A password file, not --auth=trust: this data dir may end up
  # reachable beyond localhost if run as its own CML Application (see
  # README's "two deployment modes") — trust auth would let anyone who
  # can open a TCP connection in as any role, no password needed.
  PW_FILE="$(mktemp)"
  printf '%s' "$PG_PASSWORD" > "$PW_FILE"
  "${BIN}initdb" -D "$PG_DATA_DIR" --auth=scram-sha-256 --username="$PG_USER" --pwfile="$PW_FILE"
  rm -f "$PW_FILE"

  # Listen on all interfaces and require a password on every host
  # connection — deliberately not trust-by-IP, for the same reason as
  # above. If you're running in the embedded/co-located mode (default,
  # see README) this is stricter than it needs to be for a
  # localhost-only connection, but it costs nothing and means the
  # exact same data directory is safe to promote to its own CML
  # Application later without reconfiguring auth.
  {
    echo "listen_addresses = '*'"
    echo "port = $PG_PORT"
    # Default unix_socket_directories (/var/run/postgresql) is
    # typically root-owned and not writable by whatever unprivileged
    # user a CML Application actually runs as — point it at the data
    # directory itself instead, which this same user just created and
    # definitely can write to.
    echo "unix_socket_directories = '$PG_DATA_DIR'"
  } >> "$PG_DATA_DIR/postgresql.conf"
  cat > "$PG_DATA_DIR/pg_hba.conf" <<-EOF
	local   all             all                                     scram-sha-256
	host    all             all             0.0.0.0/0               scram-sha-256
	host    all             all             ::0/0                   scram-sha-256
	EOF

  NEEDS_BOOTSTRAP=1
else
  echo "Existing data directory found at $PG_DATA_DIR — reusing it."
  NEEDS_BOOTSTRAP=0
fi

if [ "$NEEDS_BOOTSTRAP" = "1" ]; then
  # Create the app database in a one-shot background start/stop cycle
  # (createdb needs a running server; the exec below takes over as the
  # long-lived foreground process after this).
  #
  # --maintenance-db=postgres is required: with none given, createdb's
  # own default is a database named after the connecting user (here,
  # PG_USER, e.g. "itap") — which doesn't exist yet on a brand new
  # cluster, so it fails with "database ... does not exist" before it
  # ever gets to creating one. "postgres" always exists post-initdb.
  #
  # PGPASSWORD is required too: auth is scram-sha-256, not trust (see
  # above), so without it createdb blocks forever on an interactive
  # password prompt with no terminal attached to answer it.
  "${BIN}pg_ctl" -D "$PG_DATA_DIR" -o "-p $PG_PORT" -l "$PG_DATA_DIR/bootstrap.log" -w start
  PGPASSWORD="$PG_PASSWORD" "${BIN}createdb" \
    -h 127.0.0.1 -p "$PG_PORT" -U "$PG_USER" --maintenance-db=postgres "$PG_DB"
  "${BIN}pg_ctl" -D "$PG_DATA_DIR" -m fast stop
fi

echo "Starting Postgres on port $PG_PORT, data dir $PG_DATA_DIR ..."
exec "${BIN}postgres" -D "$PG_DATA_DIR" -p "$PG_PORT"
