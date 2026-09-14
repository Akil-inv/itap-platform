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
`__file__` is simply undefined and raises NameError. Instead this
relies on CML's own documented convention that an Application always
runs with its working directory set to the project root (e.g.
/home/cdsw) -- the same root the "Script" field's own path
(apps/streamlit_ui/cml_launcher.py) is relative to -- so app.py's path
relative to that same root is fixed and doesn't need __file__ at all.
"""
import os

port = os.environ["CDSW_APP_PORT"]

# The expected case (Application working directory = project root, per
# CML's own convention) first; falls back to "already inside
# apps/streamlit_ui" in case that assumption doesn't hold on some CML
# versions/configs -- either way, no reliance on __file__ (see above).
if os.path.isfile("apps/streamlit_ui/app.py"):
    app_path = "apps/streamlit_ui/app.py"
elif os.path.isfile("app.py"):
    app_path = "app.py"
else:
    raise FileNotFoundError(
        "Could not find app.py from the current working directory "
        f"({os.getcwd()}) via either 'apps/streamlit_ui/app.py' or "
        "'app.py' -- check what CWD this CML Application actually runs "
        "with and adjust cml_launcher.py's path resolution to match."
    )

os.execvp(
    "streamlit",
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
