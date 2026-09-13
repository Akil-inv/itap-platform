"""Optional: run Postgres as a background subprocess of this same
Streamlit process, so a single CML Application is entirely
self-contained — no CML-managed database service, no second CML
Application, no cross-app networking question (see
apps/postgres_service/README.md for that alternative and why this one
is the safer default when it's unconfirmed whether your CML workspace
even allows one Application to reach another over a raw TCP port).

Off by default (`services.py` falls back to SQLite, same as always).
Turn it on with `EMBED_POSTGRES=true` plus `PG_PASSWORD` — see
apps/postgres_service/README.md for the rest of the env vars and the
data-directory-must-be-persistent caveat that applies here exactly as
it does to the standalone service.

Health check / auto-relaunch: `ensure_running()` (called once, from
services.py's own cached `_build_services()`) starts Postgres and
blocks until it's ready, but does nothing if it dies later — a CML
Application restart isn't the only thing that should be able to
recover from that. `check_and_relaunch()` is a second, cheap entry
point services.py calls on *every* app rerun (Streamlit reruns the
whole script on every interaction, which is what makes "every rerun"
a reasonably fast detection window) — it polls whether the subprocess
is still alive and relaunches it if not, reusing the same PG_DATA_DIR
so no data is lost (start.sh already skips re-initializing when the
data directory exists — see its own comments).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time

import streamlit as st

_POSTGRES_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "postgres_service")
_START_TIMEOUT_SECONDS = 30
# Floor between relaunch attempts: a Postgres that dies immediately on
# every start (bad data directory, disk full, etc.) is a real problem
# to go look at -- retrying it on every single Streamlit rerun would
# just burn CPU in a tight crash loop instead of surfacing that.
_MIN_RELAUNCH_INTERVAL_SECONDS = 10

_lock = threading.Lock()
_process: subprocess.Popen | None = None
_last_relaunch_attempt = 0.0


def is_enabled() -> bool:
    return os.environ.get("EMBED_POSTGRES", "false").lower() in ("true", "1", "yes")


def database_url() -> str:
    """The DATABASE_URL to use when embedded Postgres is enabled —
    derived from the same PG_* env vars start.sh reads, so there's one
    set of settings instead of two that could drift out of sync."""
    host = "127.0.0.1"
    port = os.environ.get("PG_PORT", "5432")
    db = os.environ.get("PG_DB", "itap")
    user = os.environ.get("PG_USER", "itap")
    password = os.environ["PG_PASSWORD"]
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def _spawn() -> subprocess.Popen:
    """Starts postgres_service/start.sh as a background subprocess and
    blocks until it's accepting connections (or the subprocess exits,
    or the timeout elapses), whichever comes first. Pure — doesn't
    touch module state; callers decide what to do with the handle."""
    # Resolved to an absolute path rather than left as "bash" for
    # subprocess.Popen's own PATH lookup: PATH isn't guaranteed to be
    # set the way it is in an interactive shell inside whatever
    # container CML actually runs this in.
    bash = shutil.which("bash") or "/usr/bin/bash"
    env = dict(os.environ)
    process = subprocess.Popen(
        [bash, os.path.join(_POSTGRES_SERVICE_DIR, "start.sh")],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    port = os.environ.get("PG_PORT", "5432")
    user = os.environ.get("PG_USER", "itap")
    pg_bin_dir = os.environ.get("PG_BIN_DIR", "")
    pg_isready = os.path.join(pg_bin_dir, "pg_isready") if pg_bin_dir else "pg_isready"
    deadline = time.monotonic() + _START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Embedded Postgres exited immediately (code {process.returncode}) — "
                "check the CML Application's logs for postgres_service/start.sh output."
            )
        result = subprocess.run([pg_isready, "-p", port, "-U", user], capture_output=True)
        if result.returncode == 0:
            return process
        time.sleep(0.5)
    raise RuntimeError(
        f"Embedded Postgres did not become ready within {_START_TIMEOUT_SECONDS}s — "
        "check the CML Application's logs for postgres_service/start.sh output."
    )


@st.cache_resource
def ensure_running() -> None:
    """First start, called once (via services.py's own cached
    _build_services()) per app process. Blocks until Postgres is
    ready, or raises — a failure here should fail app startup loudly,
    not limp along with no database."""
    global _process
    with _lock:
        _process = _spawn()


def check_and_relaunch() -> None:
    """Cheap liveness check — call this on every app rerun (see
    services.py's get_services()). No-ops if embedded Postgres isn't
    enabled, or if ensure_running() hasn't launched it yet (this
    supplements that, it doesn't replace it). If the subprocess has
    died, relaunches it against the same PG_DATA_DIR, subject to the
    backoff above."""
    global _process, _last_relaunch_attempt
    if not is_enabled() or _process is None:
        return
    with _lock:
        if _process.poll() is None:
            return  # still alive
        now = time.monotonic()
        if now - _last_relaunch_attempt < _MIN_RELAUNCH_INTERVAL_SECONDS:
            return
        _last_relaunch_attempt = now
        exit_code = _process.returncode
        print(f"pg_embedded: Postgres subprocess died (exit code {exit_code}) — relaunching.")
        try:
            _process = _spawn()
        except RuntimeError as exc:
            print(f"pg_embedded: relaunch attempt failed: {exc}")
