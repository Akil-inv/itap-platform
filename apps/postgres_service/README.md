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

## The bundled Postgres binaries (`pg_bundle/`)

Unlike the Python offline wheelhouse (which hits a real, unavoidable
"built for the wrong OS/glibc" risk — see
`apps/streamlit_ui/offline_deploy/README.md`), the binaries in
`pg_bundle/` are built to sidestep that problem entirely rather than
just warn about it:

- **Linked against musl, not glibc**, with musl's own tiny runtime
  (`pg_bundle/lib/ld-musl-x86_64.so.1`) shipped alongside — these
  binaries depend on nothing from the target machine but the Linux
  kernel's syscall interface, which is stable across any remotely
  modern distro. No glibc version to match, RHEL/CDP or otherwise.
- **Not fully static** — Postgres's own extension loading
  (`dict_snowball`, `plpgsql`, both required just for `initdb`'s
  default bootstrap) needs `dlopen()` at runtime, which a truly static
  binary can't do. These are dynamically linked, just against the
  bundled musl instead of the target's glibc.
- **Relocatable to any path.** The one thing that can't be made
  relative is the ELF interpreter (the kernel requires it to be a real
  absolute path — no `$ORIGIN`, no `PATH` search, unlike RPATH). Every
  binary is linked with a long, obviously-fake placeholder interpreter
  path (~215 bytes reserved) instead of a real one;
  `patch_interpreter.py` rewrites it in place, at first use, to
  wherever `pg_bundle/` actually landed. `start.sh` runs this
  automatically (idempotent — safe to run on every start, not just the
  first) whenever it finds `pg_bundle/bin` next to itself; the other
  scripts (`backup.sh`, `restore.sh`, `healthcheck.sh`) also default
  `PG_BIN_DIR` to `pg_bundle/bin` if present, but don't re-patch —
  run/restart via `start.sh` at least once first.

Verified this session, with the sandbox's own musl runtime hidden
(simulating a target machine that doesn't have musl installed) and the
bundle copied to an arbitrary, previously-unseen path: `initdb`,
`pg_ctl start` (which internally re-execs `postgres` itself — the
scenario most likely to break under naive relocation), the full ITAP
app test suite, a 30-concurrent-writer stress test, and a full
backup → restore round trip. All passed unchanged.

**What's still genuinely unverified**: this was all built and tested
on Ubuntu 24.04 x86_64. The musl approach removes the *glibc*-matching
risk, but if your CML runtime is a different CPU architecture (arm64)
or has kernel-level restrictions this sandbox doesn't (seccomp/syscall
filtering in some hardened containers occasionally blocks syscalls
older/portable binaries rely on), that's not something this could
verify without access to the real environment. Test `pg_bundle/bin/
postgres --version` there before relying on it for anything real.

To rebuild (a newer Postgres version, or if this approach needs
revisiting): `build_postgres_bundle.sh` on an Ubuntu/Debian machine
with `apt` and `musl-tools` reproduces the whole thing — see its own
comments for exactly what it does and why. `pg_bundle/` itself is
gitignored on source branches (same convention as
`offline_deploy/wheelhouse/`) and committed on the offline-deps branch
(or your equivalent binary-artifacts branch).

If you'd rather not rely on a musl build at all: check whether
`postgres`/`initdb`/`pg_ctl` are already present on the CML box, or
whether your platform team can install `postgresql-server` (or your
distro's equivalent) directly — either sidesteps this section
entirely. Point `PG_BIN_DIR` at wherever those binaries live instead
of `pg_bundle/bin`.

## Env vars (all scripts)

| Var | Required | Default | Notes |
|---|---|---|---|
| `PG_DATA_DIR` | yes (start.sh, healthcheck.sh) | — | **Must be on storage that survives a restart/redeploy** — a container-local path that resets on every restart silently starts from an empty database each time. |
| `PG_PORT` | no | `5432` | |
| `PG_USER` | no | `itap` | |
| `PG_PASSWORD` | yes (start.sh) | — | Set once, at first init — changing it later needs `ALTER ROLE`, not just re-exporting the var. |
| `PG_DB` | no | `itap` | |
| `PG_BIN_DIR` | no | `pg_bundle/bin` if present, else `PATH` | Point elsewhere if not using the bundled binaries. |
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
