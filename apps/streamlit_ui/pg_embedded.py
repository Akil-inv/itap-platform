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
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time

import streamlit as st

_POSTGRES_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "postgres_service")
_START_TIMEOUT_SECONDS = 30


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


@st.cache_resource
def ensure_running() -> None:
    """Starts postgres_service/start.sh as a background subprocess on
    first call and blocks until it's accepting connections. Cached so
    this only happens once per app process — Streamlit reruns this
    module's top level on every interaction, but @st.cache_resource
    means the subprocess is launched exactly once, not per rerun."""
    # Resolved to an absolute path rather than left as "bash" for
    # subprocess.Popen's own PATH lookup: PATH isn't guaranteed to be
    # set the way it is in an interactive shell inside whatever
    # container CML actually runs this in.
    bash = shutil.which("bash") or "/usr/bin/bash"
    env = dict(os.environ)
    subprocess.Popen(
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
        result = subprocess.run(
            [pg_isready, "-p", port, "-U", user],
            capture_output=True,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError(
        f"Embedded Postgres did not become ready within {_START_TIMEOUT_SECONDS}s — "
        "check the CML Application's logs for postgres_service/start.sh output."
    )
