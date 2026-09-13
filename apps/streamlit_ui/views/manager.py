"""Manager's "My Team" — Phase 3 of the redesign
(docs/associate_journey_redesign.md's "Manager flow" section): scoped to
this Manager's own Assignments, split into **Current** / **Rolled Off**
tabs. Reuses the tenure battery bar (`battery.py`, same as the admin's
list) but carries **no score display of any kind, hidden or otherwise**
— per spec, "Aggregate score is never visible to a manager ... for
anyone but themselves" refers to a score a manager *gave*, on a specific
episode's own Review & Scoring tab, never a rolled-up number on this
list. This is a hard rule, not a UI nicety: don't add a hidden/eye-icon
score here the way the admin's list has one.

Clicking a name opens `views/manager_associate.py` (level 2, this
Manager's own view of one Associate) — same "level 2 page via
session_state, not a nested tab" pattern as
`views/functional_owner.py` -> `views/associate_portfolio.py`.
"""
from __future__ import annotations

from uuid import UUID

import streamlit as st
from assignment.domain import AssignmentKind
from battery import render_html as render_battery_html
from party_identity.domain import Party, PartyNotFound
from person_row import render_person_row
from rbac_scope import Viewer

from views import manager_associate


def render(services, viewer: Viewer, current_party: Party) -> None:
    selected_id = st.session_state.get("selected_manager_associate_id")
    if selected_id is not None:
        try:
            agent = services.party_repo.get(UUID(selected_id))
        except (ValueError, PartyNotFound):
            del st.session_state["selected_manager_associate_id"]
            st.rerun()
            return
        manager_associate.render(services, viewer, agent)
        return

    st.title("My Team")
    st.caption(f"Welcome back, {current_party.display_name}.")

    current_ids, rolled_off_ids = _classify(services, viewer)

    tab_current, tab_rolled_off = st.tabs(["Current", "Rolled Off"])
    with tab_current:
        _render_rows(services, current_ids, empty_message="No Associates currently tasked to you.")
    with tab_rolled_off:
        st.caption("Read-only history — associates who have since moved to a different manager.")
        _render_rows(services, rolled_off_ids, empty_message="No one has rolled off your team yet.")


def _classify(services, viewer: Viewer) -> tuple[list, list]:
    """Splits this Manager's Associates into Current / Rolled Off.

    **Current**: any Assignment of any kind (Primary/Secondary/CCA) still
    ACTIVE under this Manager.

    **Rolled Off** (judgment call — spec says "associates who've since
    moved to a different manager"; the exact detection rule was left
    open): the Associate's most recent Primary *under this Manager* has
    closed, AND they have since started a Primary under a *different*
    Manager (start date on/after that closed Primary's end date) — i.e.
    the relationship is genuinely over, not just an in-between gap. An
    Associate who merely finished a Secondary/CCA with this Manager, or
    whose Primary closed but who hasn't started anywhere else yet
    (Available/Unassigned), does not show up in either tab — they simply
    aren't "this Manager's team" right now in a way either tab describes.
    """
    my_assignments = services.assignment_repo.list_by_manager(viewer.party_id)
    agent_ids = {a.agent_id for a in my_assignments}

    current_ids: list = []
    rolled_off_ids: list = []
    for agent_id in agent_ids:
        all_assignments = services.assignment_repo.list_by_agent(agent_id)
        mine = [a for a in all_assignments if a.manager_id == viewer.party_id]

        if any(a.state.value == "active" for a in mine):
            current_ids.append(agent_id)
            continue

        my_primaries = sorted(
            (a for a in mine if a.kind == AssignmentKind.PRIMARY), key=lambda a: a.start_date
        )
        if not my_primaries:
            continue
        last_primary = my_primaries[-1]
        if last_primary.state.value != "closed":
            continue

        moved_on_cutoff = last_primary.end_date or last_primary.start_date
        moved_on = any(
            a.kind == AssignmentKind.PRIMARY
            and a.manager_id != viewer.party_id
            and a.start_date >= moved_on_cutoff
            for a in all_assignments
        )
        if moved_on:
            rolled_off_ids.append(agent_id)

    return current_ids, rolled_off_ids


def _render_rows(services, agent_ids: list, empty_message: str) -> None:
    if not agent_ids:
        st.write(empty_message)
        return

    agents = sorted(
        (services.party_repo.get(agent_id) for agent_id in agent_ids),
        key=lambda p: p.display_name,
    )
    for agent in agents:
        all_assignments = services.assignment_repo.list_by_agent(agent.id)
        battery_html = render_battery_html(all_assignments, party_repo=services.party_repo)
        profile = services.catalog_service.get_profile(agent.id)
        # Deliberately no score column here — see this module's
        # docstring: managers never see the aggregate score, not even
        # hidden behind a reveal. One coherent card — avatar, name,
        # tenure meter — rather than a raw button next to a floating
        # battery bar.
        clicked, _extra_cols = render_person_row(
            key=f"manager_{agent.id}",
            display_name=agent.display_name,
            photo_url=profile.photo_url if profile else None,
            battery_html=battery_html,
        )
        if clicked:
            st.session_state["selected_manager_associate_id"] = str(agent.id)
            st.rerun()
