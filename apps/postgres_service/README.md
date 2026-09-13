# Postgres service (self-managed, no CML-managed DB required)

For when your CML workspace doesn't provision a database service —
this runs a real, unmodified Postgres, self-contained: its own data
directory, its own start/backup/restore/health scripts, no dependency
on anything CML doesn't already give you (a place to run a process and
a place to persist files).

The app's own SQL adapters (`capabilities/*/src/*/adapters/sql.py`)
were already written in SQLAlchemy Core with no Postgres-only features
specifically so this drop-in works with zero application code changes
— `DATABASE_URL` is the only thing that has to point here instead of
at SQLite.

## Why this exists, and the two ways to run it

The architecture (`docs/architecture.md`) always intended Postgres as
the system of record. What was never resolved is *how* to get a
Postgres to point at, given the CML platform team won't provision one.
There are two shapes this can take:

1. **Embedded (default, recommended to start with)** — Postgres runs
   as a background subprocess of the Streamlit app's own CML
   Application (`apps/streamlit_ui/pg_embedded.py`). One CML
   Application, no new platform dependency, connects over
   `127.0.0.1` so there is no networking question to answer. Turn it
   on with `EMBED_POSTGRES=true` (see `apps/streamlit_ui/README.md`
   for the exact env vars).

2. **Standalone, as its own CML Application** — run `start.sh` as that
   Application's entrypoint, and point the Streamlit app's
   `DATABASE_URL` at it. This is what "as a second app" in the
   project's notes refers to. **It depends on one thing this project
   has never confirmed: whether your CML workspace lets one
   Application reach another over a raw TCP port** (`docs/
   architecture.md`'s open platform question #2 — CML Applications
   are generally an HTTP-ingress model, and raw TCP between
   Applications may not be exposed at all). Test that specifically
   before committing to this shape; embedded mode sidesteps the
   question entirely and is otherwise identical (same scripts, same
   backup/restore, same data-directory requirements) — moving from one
   to the other later is a `DATABASE_URL`/port change, not a rewrite.

Either way, the scripts here don't care where they're invoked from.

## Getting real Postgres binaries onto your CML box

Nothing here bundles a Postgres binary — a binary built in this
sandbox (Ubuntu 24.04, glibc 2.39) is very likely to fail to run at
all on a RHEL/CDP-family CML runtime with an older glibc (the same
class of problem the Python offline wheelhouse hit with manylinux
tags — see `apps/streamlit_ui/offline_deploy/README.md` — except
there's no equivalent "build for any target from one machine" trick
for a compiled C program; it has to run on something that actually
matches). In order of preference:

1. Check whether `postgres`/`initdb`/`pg_ctl` are already present on
   the CML box (`which postgres` in a CML terminal, or check whatever
   your base image ships) — some enterprise Linux images already
   carry the client tools or even a server package.
2. If your CML terminal has a package manager with any repo access
   (`yum`/`dnf`/`apt`), install `postgresql-server` (or your distro's
   equivalent) directly there — this is the simplest ask to make of
   your platform team ("install this one package") and sidesteps
   every binary-compatibility question.
3. As a last resort, build Postgres from source on a machine that
   actually matches your CML runtime's OS/glibc (check with `cat
   /etc/os-release` and `ldd --version` in a CML terminal first), and
   transfer the resulting `bin/`+`lib/` install prefix in — same
   "build/download elsewhere, upload the result" pattern as the Python
   wheelhouse.

Whichever of the three gets you working binaries, point `PG_BIN_DIR`
at their directory (or just make sure they're on `PATH`) — every
script here resolves `initdb`/`postgres`/`pg_dump`/etc. through
`PG_BIN_DIR` first, PATH otherwise.

## Env vars (all scripts)

| Var | Required | Default | Notes |
|---|---|---|---|
| `PG_DATA_DIR` | yes (start.sh, healthcheck.sh) | — | **Must be on storage that survives a restart/redeploy** — a container-local path that resets on every restart silently starts from an empty database each time. |
| `PG_PORT` | no | `5432` | |
| `PG_USER` | no | `itap` | |
| `PG_PASSWORD` | yes (start.sh) | — | Set once, at first init — changing it later needs `ALTER ROLE`, not just re-exporting the var. |
| `PG_DB` | no | `itap` | |
| `PG_BIN_DIR` | no | (use `PATH`) | See above. |
| `PGPASSWORD` | yes (backup.sh, restore.sh) | — | Read directly by `pg_dump`/`pg_restore`/`createdb`. |
| `PG_BACKUP_DIR` | yes (backup.sh) | — | Ideally a different physical volume than `PG_DATA_DIR`. |
| `PG_BACKUP_RETENTION_DAYS` | no | `14` | |
| `PG_BACKUP_FILE` | yes (restore.sh) | — | The `.dump` file to restore. |
| `PG_RESTORE_DB` | no | `itap_restore` | Deliberately not `itap` — see restore.sh. |
| `DISK_WARN_PERCENT` | no | `85` | healthcheck.sh warning threshold. |

## Backups

Schedule `backup.sh` as a recurring CML Job (nightly is a reasonable
default for this app's write volume). It writes a timestamped,
`pg_restore`-only dump and prunes anything older than
`PG_BACKUP_RETENTION_DAYS`. **Practice a restore before you need one**
— `restore.sh` always targets a separate database (`PG_RESTORE_DB`,
default `itap_restore`), never overwrites the live `itap` database, so
a practice run is safe to do at any time:

```bash
PG_BACKUP_FILE=/path/to/itap_20260101T000000Z.dump PGPASSWORD=... bash restore.sh
psql -h 127.0.0.1 -p "$PG_PORT" -U itap -d itap_restore -c "select count(*) from parties;"
```

Verified end-to-end in this session: seeded data → `backup.sh` →
dropped/replaced target DB → `restore.sh` → identical row counts and
content. See the session's own verification for the exact commands.

## Downtime / maintenance runbook

For planned maintenance (an OS patch, a Postgres upgrade, moving data
directories):

1. **Tell people first** — there's no maintenance-mode banner in the
   app yet; a Manager or Associate mid-form-submission during a
   restart just sees a connection error.
2. **Take a fresh backup** (`backup.sh`) — always, even for routine
   maintenance, before touching anything.
3. **Stop the Streamlit app first, then Postgres** — stopping Postgres
   while the app is still up just turns every page into a stream of
   connection errors instead of a clean "app is down" state.
4. Do the maintenance.
5. **Start Postgres, run `healthcheck.sh`, confirm OK, then start the
   Streamlit app.** Don't start the app against a Postgres you haven't
   confirmed is actually accepting connections — `get_services()`
   fails loudly if it can't connect, but "loudly" still means every
   user sees a broken app in the meantime.
6. Spot-check: sign in, confirm recent data (from before the
   maintenance window) is intact.

For *unplanned* downtime (the process died, the host rebooted): if
you're running the **embedded** mode, restarting the Streamlit CML
Application restarts Postgres with it (same subprocess lifecycle) —
nothing extra to do beyond confirming `PG_DATA_DIR` really did
survive whatever happened. If you're running **standalone**, your CML
Application's own restart policy governs whether `start.sh` gets
re-invoked automatically; confirm that's configured before relying on
it.

## What's NOT handled here

- **Replication / high availability** — this is a single Postgres
  instance. If it's down, the app is down. Nothing here sets up a
  standby or failover.
- **Automated failure alerting** — `healthcheck.sh`'s exit code is
  meant to be wired into whatever your CML setup uses to notify on a
  failed scheduled Job; nothing here sends that notification itself.
- **Encryption at rest** — depends entirely on whatever your CML
  persistent storage already provides; this doesn't add its own.
