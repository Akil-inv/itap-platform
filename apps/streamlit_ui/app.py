"""ITAP Streamlit UI.

Identity here is a dev-mode stand-in: a sidebar picker over existing
Parties, role derived from party_type. Real auth (SSO passthrough vs a
dedicated login) is an open platform question — see
docs/architecture.md "Open platform questions" — and this picker is the
one thing to replace once that's answered. Everything below it (services,
views, RBAC enforcement) does not change when real auth arrives; it only
needs a Viewer, however that gets constructed.
"""
from __future__ import annotations

import streamlit as st
from party_identity.domain import Party
from rbac_scope import Role, Viewer

import theme
from party_helpers import party_label
from services import get_services
from views import agent as agent_view
from views import functional_owner as owner_view
from views import manager as manager_view

st.set_page_config(page_title="ITAP", layout="wide")
theme.inject()

services = get_services()
party_repo = services.party_repo

st.sidebar.title("ITAP")


def _seed_demo_data() -> None:
    owner = Party(party_type="functional_owner", display_name="Priya")
    manager_a = Party(party_type="manager", display_name="Alex")
    manager_b = Party(party_type="manager", display_name="Bailey")
    agent_a = Party(party_type="agent", display_name="Casey")
    agent_b = Party(party_type="agent", display_name="Dana")

    for party in (owner, manager_a, manager_b, agent_a, agent_b):
        party_repo.add(party)

    from datetime import date

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
    st.sidebar.info("No Parties yet.")
    if st.sidebar.button("Seed demo data"):
        _seed_demo_data()
        st.rerun()
    st.title("Welcome to ITAP")
    st.write(
        "No Agents, Managers, or Functional Owners exist yet. Click "
        "**Seed demo data** in the sidebar to create a small demo world, "
        "or onboard the first Functional Owner directly against the "
        "database to get started for real."
    )
    st.stop()

labels = {party_label(p): p for p in all_parties}
chosen_label = st.sidebar.selectbox("View as", list(labels.keys()))
current_party = labels[chosen_label]
viewer = Viewer(party_id=current_party.id, role=Role(current_party.party_type))

st.sidebar.caption(f"party_id: {current_party.id}")
st.sidebar.divider()
st.sidebar.caption(
    "Identity here is a dev-mode stand-in — see docs/architecture.md "
    "for the real-auth open question."
)

if viewer.role == Role.FUNCTIONAL_OWNER:
    owner_view.render(services, viewer)
elif viewer.role == Role.MANAGER:
    manager_view.render(services, viewer, current_party)
elif viewer.role == Role.AGENT:
    agent_view.render(services, viewer, current_party)
