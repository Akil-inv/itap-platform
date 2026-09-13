"""ITAP Streamlit UI — app shell.

Identity/routing model: a landing page (home.py) is the one place a
person is chosen, stored in st.session_state — not a sidebar dropdown
that doubles as page navigation. This is the dev-mode stand-in for real
auth. There are two real-auth paths ahead of it: `sso_auth.py` (CML SSO
passthrough, checked right here in app.py, first on every run — see its
docstring for the mechanism) and `ad_auth.py` (a real username/password
login bound against Active Directory, checked inside home.py itself
when there's no SSO header). Either one identifying a signed-in person
skips the picker entirely: real auth means never choosing who you are.
Everything below the identity resolution (services, views, RBAC
enforcement) does not change either way; it only needs a Viewer,
however that gets constructed.

Page headings are product/task-oriented ("My Team", "My Journey",
"Workforce Overview"), not the signed-in person's name or role — the
person is shown as a small "Welcome back" line under the heading and in
the persistent header's identity chip, not as the page's identity.
"""
from __future__ import annotations

import os
from datetime import date
from uuid import UUID

import streamlit as st
from rbac_scope import Role, Viewer

import generate_demo_workbook
import home
import sso_auth
import theme
import user_manual
from services import get_services
from role_labels import ROLE_DISPLAY_NAME
from views import agent as agent_view
from views import functional_owner as owner_view
from views import manager as manager_view

st.set_page_config(page_title="ITAP", layout="wide")
theme.inject()

services = get_services()
party_repo = services.party_repo

# Checked first, on every run, before anything else touches identity.
# None whenever there's no CML proxy in front asserting a signed-in
# identity (local `streamlit run`, or SSO passthrough not enabled for
# this workspace) — everything below falls back to the dev-mode picker
# exactly as before in that case. See sso_auth.py's docstring for the
# mechanism and what still needs confirming with a CML admin before
# trusting this in production.
sso_identity = sso_auth.get_sso_identity()

all_parties = (
    party_repo.list_by_type("functional_owner")
    + party_repo.list_by_type("manager")
    + party_repo.list_by_type("agent")
)

if not all_parties:
    # Phase 5: "Seed demo data" is gone (docs/associate_journey_redesign.md,
    # "No more Seed demo data button") — trying the product and setting up
    # a real client are now the exact same path: download a workbook,
    # upload it through Bulk Setup. This one only differs in content
    # (fabricated names + a full year of rotation history), never in code
    # path.
    st.title("Welcome to ITAP")
    st.write(
        "No Associates, Managers, or Functional Owners exist yet. A fresh "
        "deployment starts empty — bring your team to life by uploading a "
        "Setup Workbook through **Bulk Setup** once you sign in, or "
        "download a ready-made demo dataset below to see a full year of "
        "rotation history without typing anything in by hand."
    )
    st.download_button(
        "Download demo dataset (.xlsx)",
        data=generate_demo_workbook.build_demo_workbook(),
        file_name="itap_demo_dataset.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.caption(
        "After downloading: sign in as the first Admin below, then use "
        "Workforce Overview → Bulk Setup to upload it — same upload path "
        "a real client's file goes through."
    )
    home.render(services)
    st.stop()

if sso_identity:
    # A real signed-in identity is asserted for this request — resolve
    # it to a Party on every run (never trust whatever a prior dev-mode
    # "Switch person" click may have left sitting in session_state) so
    # nobody can use the picker to look at someone else's data while
    # actually authenticated as themselves via SSO.
    matched = sso_auth.find_party_by_sso_identity(party_repo, sso_identity)
    if matched is None:
        st.title("ITAP")
        st.error(
            f"Signed in via SSO as **{sso_identity}**, but no ITAP account "
            "is provisioned for that identity yet. Ask your ITAP Admin to "
            "onboard you (matching this email), then refresh this page."
        )
        st.stop()
    st.session_state["viewer_party_id"] = str(matched.id)
else:
    viewer_party_id = st.session_state.get("viewer_party_id")
    if viewer_party_id is None:
        home.render(services)
        st.stop()

viewer_party_id = st.session_state["viewer_party_id"]

# DEV_MODE gates identity switching. Default true (this whole picker is
# a stand-in for real auth, per the docstring above) — but a misconfigured
# "production-ish" deployment can set ITAP_DEV_MODE=false, which at least
# removes the one-click "become anyone" affordance until real auth exists.
# This is a safety valve, not a security boundary: it doesn't protect
# the underlying service calls, which have no auth of their own yet.
# Forced off whenever an SSO identity is present, or this session
# authenticated via home.py's AD login form (home.py sets
# "authenticated_via" on a successful bind) — regardless of the env var,
# since a real logged-in user must never be able to fall back to the
# picker and impersonate someone else, misconfiguration or not.
DEV_MODE = (
    not sso_identity
    and not st.session_state.get("authenticated_via")
    and os.environ.get("ITAP_DEV_MODE", "true").lower() not in ("false", "0", "no")
)

try:
    current_party = party_repo.get(UUID(viewer_party_id))
except Exception:
    del st.session_state["viewer_party_id"]
    st.rerun()

try:
    viewer = Viewer(party_id=current_party.id, role=Role(current_party.party_type))
except ValueError:
    st.error(
        f"'{current_party.display_name}' has an unrecognized role "
        f"({current_party.party_type!r}) and can't be signed in."
    )
    if DEV_MODE and st.button("Switch person"):
        del st.session_state["viewer_party_id"]
        st.rerun()
    st.stop()

header_left, header_manual, header_switch = st.columns([5, 1, 1])
with header_left:
    st.markdown(
        '<div style="font-size:var(--itap-font-size-xs); color:var(--itap-neutral-600);">'
        f"ITAP &nbsp;·&nbsp; Signed in as <strong>{current_party.display_name}</strong> "
        f"({ROLE_DISPLAY_NAME[viewer.role]})</div>",
        unsafe_allow_html=True,
    )
with header_manual:
    with st.popover("📖 User Manual", width='stretch'):
        user_manual.render(viewer.role)
with header_switch:
    if DEV_MODE and st.button("Switch person", width='stretch'):
        del st.session_state["viewer_party_id"]
        st.rerun()

if viewer.role == Role.FUNCTIONAL_OWNER:
    owner_view.render(services, viewer, current_party)
elif viewer.role == Role.MANAGER:
    manager_view.render(services, viewer, current_party)
elif viewer.role == Role.AGENT:
    agent_view.render(services, viewer, current_party)
