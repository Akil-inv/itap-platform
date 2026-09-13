"""CML SSO passthrough — the real-auth replacement for `home.py`'s
dev-mode "pick who you are" picker, per docs/architecture.md's "Open
platform questions" (now resolved for this one item).

**Mechanism**: a CML Application sits behind CML's own authenticating
reverse proxy. When SSO passthrough is enabled for the workspace,
Cloudera's own documentation describes the proxy injecting the signed-in
user's identity into a `Remote-User` HTTP header on every request it
forwards to the application — the same `REMOTE_USER`-style convention
used elsewhere in the Hadoop/Cloudera ecosystem. Streamlit exposes
inbound request headers via `st.context.headers` (added in Streamlit
1.37+; this app pins >=1.30 in requirements.txt but a CML Runtime image
should be built against a version that includes it).

**What still needs confirming with your CML admin/platform team before
trusting this in production** (this is exactly the kind of thing
docs/architecture.md's "Open platform questions" section tracks):

1. **The exact header name and casing.** `Remote-User` is Cloudera's own
   documented default, but a given workspace's ingress/gateway
   configuration could use something else. Override it with the
   `SSO_HEADER_NAME` environment variable if so — no code change needed.
2. **That the header can't be spoofed.** This only provides real
   authentication if CML's proxy *strips* any client-supplied header of
   this same name from the raw incoming request before setting its own
   — otherwise anyone who can reach the Application directly (bypassing
   the proxy) could hand-craft this header and impersonate anyone. Ask
   your CML admin to confirm this is how the workspace's ingress is
   configured. Until confirmed, treat this as "identifies who's likely
   signed in," not as a hardened security boundary — same caveat
   `ITAP_DEV_MODE` already carries elsewhere in this app.
3. **What the header's value actually is** — a login/username, or an
   email address. This module matches it against each Party's
   `attributes["email"]` (the existing convention docs/architecture.md
   already flags as the intended SSO-matching field — see "No field yet
   reserved for an external identity"). If your workspace's header
   carries a bare username rather than an email, onboard people with
   that same string in the email field (bulk import and the onboarding
   forms both accept any string there; nothing validates it as a real
   email address) rather than their real email.

When no such header is present at all (plain local `streamlit run`, or
a CML Runtime with SSO passthrough not enabled) `get_sso_identity()`
returns None and `app.py` falls back to today's dev-mode picker
unchanged — this module only ever *adds* an auto-identification path in
front of it, it doesn't remove the fallback.
"""
from __future__ import annotations

import os
from typing import Optional

import streamlit as st
from party_identity.domain import Party
from party_identity.ports import PartyRepo

SSO_HEADER_NAME = os.environ.get("SSO_HEADER_NAME", "Remote-User")

_PARTY_TYPES = ("functional_owner", "manager", "agent")


def get_sso_identity() -> Optional[str]:
    """The signed-in identity CML's proxy asserts for this request, or
    None if the header is absent (no proxy in front, or SSO passthrough
    isn't enabled for this workspace)."""
    try:
        headers = st.context.headers
    except Exception:
        return None
    value = headers.get(SSO_HEADER_NAME)
    value = value.strip() if value else None
    return value or None


def find_party_by_sso_identity(party_repo: PartyRepo, identity: str) -> Optional[Party]:
    """Matches the SSO identity against every onboarded Party's
    `attributes["email"]`, case-insensitively — the same natural-key
    field `bulk_import.py` already uses to match/update people on
    re-upload, reused here rather than adding a new identity field.
    Scans in-process (there's no `list_all`/find-by-attribute on
    `PartyRepo` — the party counts in a real deployment are small enough
    that this is the same "scan and match at the app layer" pattern
    `bulk_import._find_or_upsert_party` already uses, not a new one)."""
    needle = identity.strip().lower()
    for party_type in _PARTY_TYPES:
        for party in party_repo.list_by_type(party_type):
            email = party.attributes.get("email")
            if email and email.strip().lower() == needle:
                return party
    return None
