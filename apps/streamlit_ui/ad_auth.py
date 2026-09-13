"""A real username + password login, authenticating directly against
your corporate Active Directory via LDAP bind — for deployments where
CML SSO passthrough (`sso_auth.py`) isn't available yet, or where the
app needs to run somewhere outside CML's own proxy entirely. Binding
*is* the authentication check: a wrong password fails the bind and
this returns None. No password is ever stored or compared by ITAP
itself.

**Config, none of it guessable from this codebase — get these from
your AD/IT team, and test against a real account before relying on
this**: this session has no real Active Directory to test a bind
against, so everything below is a configuration point, not a verified
fact about your environment.

- `AD_SERVER` — hostname or IP of a domain controller (or an
  SSO-friendly LDAP endpoint your IT team points you to), e.g.
  "dc01.corp.example.com". Unset (the default) means AD login is off
  entirely — `is_configured()` returns False and `home.py` falls back
  to the dev-mode picker, unchanged.
- `AD_PORT` (default 636) / `AD_USE_SSL` (default true) — 636 is LDAPS
  (implicit TLS); some environments instead use 389 with StartTLS,
  which this module does not implement — ask your AD team which your
  domain controllers expect. **Do not run this against plain port 389
  without SSL/StartTLS in production** — the password goes over the
  wire in the clear otherwise.
- `AD_DOMAIN` — the UPN suffix used to build the bind principal when a
  user types a bare username, e.g. "CORP.EXAMPLE.COM" turns "jdoe" into
  "jdoe@CORP.EXAMPLE.COM". A user typing their full
  "jdoe@corp.example.com" or "CORP\\jdoe" bypasses this entirely — both
  forms are passed through as-is if the input already contains "@" or
  "\\\\".
- `AD_BASE_DN` — search base for the follow-up lookup of the
  authenticated user's email/display name, e.g.
  "DC=corp,DC=example,DC=com". Optional: without it, `authenticate()`
  still confirms the password is correct but returns `email=None`, and
  the caller can't match the person to a Party — see `home.py`'s use of
  this module for why that matters.

Uses `ldap3` (pure Python, no system libldap/openldap build dependency
— unlike `python-ldap` — which is exactly why it was picked here: no
compiled extension to worry about across the offline-bundle's Python
version/platform combinations)."""
from __future__ import annotations

import os
import ssl
from dataclasses import dataclass

from ldap3 import ALL, SIMPLE, Connection, Server, Tls

AD_SERVER = os.environ.get("AD_SERVER")
AD_PORT = int(os.environ.get("AD_PORT", "636"))
AD_USE_SSL = os.environ.get("AD_USE_SSL", "true").lower() not in ("false", "0", "no")
AD_DOMAIN = os.environ.get("AD_DOMAIN", "")
AD_BASE_DN = os.environ.get("AD_BASE_DN", "")


@dataclass
class ADUser:
    username: str
    email: str | None
    display_name: str | None


def is_configured() -> bool:
    return bool(AD_SERVER)


def _build_principal(username: str) -> str:
    if "@" in username or "\\" in username:
        return username
    return f"{username}@{AD_DOMAIN}" if AD_DOMAIN else username


def authenticate(username: str, password: str) -> ADUser | None:
    """Attempts an LDAP bind as `username`/`password` against the
    configured AD server. Returns an ADUser on success (email/
    display_name populated only if AD_BASE_DN is set and the follow-up
    search finds them), or None on any failure — bad password,
    unreachable server, not configured. Deliberately never raises and
    never distinguishes *why* it failed in its return value: a login
    form should show the same generic "invalid credentials" either way,
    not leak whether the account exists or the server is unreachable."""
    if not is_configured() or not username or not password:
        return None

    principal = _build_principal(username)

    try:
        tls = Tls(validate=ssl.CERT_REQUIRED) if AD_USE_SSL else None
        server = Server(AD_SERVER, port=AD_PORT, use_ssl=AD_USE_SSL, tls=tls, get_info=ALL)
        conn = Connection(server, user=principal, password=password, authentication=SIMPLE)
        if not conn.bind():
            return None

        email = None
        display_name = None
        if AD_BASE_DN:
            conn.search(
                AD_BASE_DN,
                f"(userPrincipalName={principal})",
                attributes=["mail", "displayName"],
            )
            if conn.entries:
                entry = conn.entries[0]
                email = str(entry.mail) if "mail" in entry and entry.mail else None
                display_name = str(entry.displayName) if "displayName" in entry and entry.displayName else None

        conn.unbind()
        return ADUser(username=username, email=email, display_name=display_name)
    except Exception:  # noqa: BLE001 — see this function's docstring:
        # deliberately never raises, and never distinguishes why.
        return None
