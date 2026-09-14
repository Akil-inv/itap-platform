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

It also does NOT hardcode any single relative path to app.py -- CML's
actual working directory for a Script turned out to move around across
attempts on the same real deployment: first confirmed as the project
root itself (/home/cdsw, with code one level below at
itap-platform/apps/streamlit_ui/app.py), then later observed to be
somewhere with the itap-platform folder one level ABOVE the working
directory instead (e.g. cwd already inside itap-platform, or inside
apps/streamlit_ui itself) -- rather than keep guessing a single fixed
layout, this checks a small, fixed set of candidate roots relative to
cwd covering every layout actually seen: cwd itself (covers "cwd IS
apps/streamlit_ui", i.e. app.py is directly "app.py"), cwd's immediate
subdirectories (covers "extracted zip into a named subfolder directly
under cwd"), and cwd's parent and grandparent (covers "cwd is already
one or two levels inside the project root"). Each candidate root is
checked for both "app.py" directly and "apps/streamlit_ui/app.py"
under it. This stays cheap -- a handful of specific path checks plus
one shallow os.listdir(cwd), no recursive walk into the 100MB+
wheelhouse tree.

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
parent = os.path.dirname(cwd)
grandparent = os.path.dirname(parent)

roots = [cwd, parent, grandparent]
for name in sorted(os.listdir(cwd)):
    full = os.path.join(cwd, name)
    if os.path.isdir(full):
        roots.append(full)

candidates = []
for root in roots:
    candidates.append(os.path.join(root, "app.py"))
    candidates.append(os.path.join(root, "apps", "streamlit_ui", "app.py"))

app_path = next((c for c in candidates if os.path.isfile(c)), None)
if app_path is None:
    raise FileNotFoundError(
        f"Could not find app.py starting from the current working "
        f"directory ({cwd}). Checked: {candidates}. Find app.py's "
        f"actual absolute path on the box (e.g. from a Session: "
        f"find /home/cdsw -name app.py) and add it explicitly to "
        f"cml_launcher.py's candidates list."
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
