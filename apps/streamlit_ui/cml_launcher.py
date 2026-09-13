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
"""
import os

port = os.environ["CDSW_APP_PORT"]
os.execvp(
    "streamlit",
    [
        "streamlit",
        "run",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py"),
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
