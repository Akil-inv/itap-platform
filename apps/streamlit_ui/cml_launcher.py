"""Entrypoint for running this app as a CML Application.

A CML Application doesn't let you choose a port — it assigns one via
the `CDSW_APP_PORT` env var and proxies to it on `127.0.0.1`, so
`streamlit run app.py` with no flags (which defaults to port 8501 and
binds all interfaces) won't be reachable through CML's proxy. Point a
CML Application's "Script" field at this file instead of app.py
directly; it just execs streamlit with the flags CML actually needs.

CORS/XSRF protection is disabled because CML's own proxy sits in front
of this (serving the app inside an iframe on its own domain), which
Streamlit's default same-origin checks don't expect — CML's proxy
layer is the access boundary here, not these checks.

Path resolution: this does NOT use `__file__` to find app.py, on
purpose. CML doesn't run an Application's Script as a normal `python3
script.py` process -- it executes the file's contents in a cell-like
context (visible as "Cell In[1], line N" in a CML traceback), where
`__file__` is simply undefined and raises NameError.

It also does NOT hardcode "apps/streamlit_ui/app.py" relative to the
working directory -- an earlier version of this file did, and broke
the moment the extracted zip/tar landed in a named subfolder (e.g.
/home/cdsw/itap-platform-offline-deps/apps/streamlit_ui/app.py) rather
than directly under the project root, since that's exactly what a
plain "unzip" leaves you with (the zip's top-level folder is whatever
GitHub named the archive, not "apps"). Instead this searches: the
working directory itself, then each of its immediate subdirectories,
for an "apps/streamlit_ui/app.py" suffix -- one level of nesting
covers "extracted zip into an extra folder," which is the actual
failure mode this hit, without an expensive deep/recursive search
(the project directory can contain 100MB+ of wheelhouse files, which a
recursive glob would waste time walking through).

Subprocess, not exec: this launches streamlit as a genuine CHILD
process and blocks waiting on it -- it does NOT use os.execvp() to
replace the current process image, even though that looks like the
more obvious choice for "become streamlit." The reason: CML runs this
Script inside a real Jupyter kernel process, which CML's kernel
gateway monitors via a heartbeat (this is the same mechanism behind
the __file__ NameError above -- "Cell In[1]" is literally a Jupyter
cell). os.execvp() replaces that entire process image with streamlit,
which means the kernel process the gateway is monitoring simply
vanishes the instant it succeeds. The gateway sees the heartbeat die,
restarts a fresh kernel, which re-runs this script, which execs into
streamlit again, killing that kernel too -- an infinite silent
crash-loop ("Kernel Restarted... restarting kernel (N/5)" in Container
Logs, with NOTHING in Application Logs, because execvp succeeding is
exactly the problem; there's no Python exception to catch or log).
Running streamlit as a child subprocess instead keeps the original
kernel process --  and its heartbeat -- alive for as long as this
script blocks on the child, which is indefinitely (streamlit itself
doesn't exit under normal operation).
"""
import os
import subprocess
import sys

port = os.environ["CDSW_APP_PORT"]
cwd = os.getcwd()

REL_APP_PATH = os.path.join("apps", "streamlit_ui", "app.py")

candidates = [REL_APP_PATH]
for name in sorted(os.listdir(cwd)):
    full = os.path.join(cwd, name)
    if os.path.isdir(full):
        candidates.append(os.path.join(name, REL_APP_PATH))

app_path = next((c for c in candidates if os.path.isfile(c)), None)
if app_path is None:
    raise FileNotFoundError(
        f"Could not find apps/streamlit_ui/app.py under the current "
        f"working directory ({cwd}) or any of its immediate "
        f"subdirectories. Checked: {candidates}. If the extracted "
        f"code is nested more than one folder deep, adjust "
        f"cml_launcher.py's search to match."
    )

result = subprocess.run(
    [
        "streamlit",
        "run",
        app_path,
        "--server.port",
        port,
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--server.enableCORS",
        "false",
        "--server.enableXsrfProtection",
        "false",
    ],
)
sys.exit(result.returncode)
