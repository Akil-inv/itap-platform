"""ITAP Streamlit UI — app shell.

Identity/routing model: a landing page (home.py) is the one place a
person is chosen, stored in st.session_state — not a sidebar dropdown
that doubles as page navigation. Real auth (SSO passthrough vs a
dedicated login) is an open platform question — see
docs/architecture.md "Open platform questions" — and home.py's sign-in
step is the one thing to replace once that's answered. Everything below
it (services, views, RBAC enforcement) does not change when real auth
arrives; it only needs a Viewer, however that gets constructed.

Page headings are product/task-oriented ("My Team", "My Journey",
"Workforce Overview"), not the signed-in person's name or role — the
person is shown as a small "Welcome back" line under the heading and in
the persistent header's identity chip, not as the page's identity.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

import streamlit as st
from party_identity.domain import Party
from rbac_scope import Role, Viewer

import home
import theme
from services import get_services
from views import agent as agent_view
from views import functional_owner as owner_view
from views import manager as manager_view

st.set_page_config(page_title="ITAP", layout="wide")
theme.inject()

services = get_services()
party_repo = services.party_repo


def _seed_demo_data() -> None:
    owner = Party(party_type="functional_owner", display_name="Priya")
    manager_a = Party(party_type="manager", display_name="Alex")
    manager_b = Party(party_type="manager", display_name="Bailey")
    agent_a = Party(party_type="agent", display_name="Casey")
    agent_b = Party(party_type="agent", display_name="Dana")

    for party in (owner, manager_a, manager_b, agent_a, agent_b):
        party_repo.add(party)

    services.assignment_service.create_assignment(agent_a.id, manager_a.id, date(2026, 1, 1))
    services.assignment_service.create_assignment(agent_b.id, manager_b.id, date(2026, 6, 1))
    # Cross-team bifurcation demo: Casey also reports to Bailey concurrently.
    services.assignment_service.create_assignment(agent_a.id, manager_b.id, date(2026, 2, 1))


all_parties = (
    party_repo.list_by_type("functional_owner")
    + party_repo.list_by_type("manager")
    + party_repo.list_by_type("agent")
)

if not all_parties:
    st.title("Welcome to ITAP")
    st.write(
        "No Agents, Managers, or Functional Owners exist yet. Click "
        "below to create a small demo world, or onboard the first "
        "Functional Owner directly against the database to get started "
        "for real."
    )
    if st.button("Seed demo data"):
        _seed_demo_data()
        st.rerun()
    st.stop()

viewer_party_id = st.session_state.get("viewer_party_id")

if viewer_party_id is None:
    home.render(services)
    st.stop()

try:
    current_party = party_repo.get(UUID(viewer_party_id))
except Exception:
    del st.session_state["viewer_party_id"]
    st.rerun()

viewer = Viewer(party_id=current_party.id, role=Role(current_party.party_type))

header_left, header_right = st.columns([5, 1])
with header_left:
    st.markdown(
        f'<div style="font-size:0.85rem; color:#6B7280;">'
        f"ITAP &nbsp;·&nbsp; Signed in as <strong>{current_party.display_name}</strong> "
        f"({viewer.role.value.replace('_', ' ')})</div>",
        unsafe_allow_html=True,
    )
with header_right:
    if st.button("Switch person", width='stretch'):
        del st.session_state["viewer_party_id"]
        st.rerun()

if viewer.role == Role.FUNCTIONAL_OWNER:
    owner_view.render(services, viewer, current_party)
elif viewer.role == Role.MANAGER:
    manager_view.render(services, viewer, current_party)
elif viewer.role == Role.AGENT:
    agent_view.render(services, viewer, current_party)
