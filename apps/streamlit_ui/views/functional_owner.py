from __future__ import annotations

from datetime import date

import streamlit as st
from assignment.domain import DuplicateAssignment
from party_identity.domain import Party
from rbac_scope import Viewer

import org_tree
from party_helpers import disambiguate_labels, safe_get_name


def render(services, viewer: Viewer, current_party: Party) -> None:
    st.title("Workforce Overview")
    st.caption(f"Welcome back, {current_party.display_name}.")

    tabs = st.tabs(
        [
            "All Assignments",
            "Org Structure",
            "Onboard & Assign",
            "Overdue",
            "Manager Handoff",
            "Consolidated Scores",
        ]
    )

    with tabs[0]:
        _all_assignments(services, viewer)
    with tabs[1]:
        _org_structure(services, viewer)
    with tabs[2]:
        _onboard_and_assign(services)
    with tabs[3]:
        _overdue(services, viewer)
    with tabs[4]:
        _manager_handoff(services, viewer)
    with tabs[5]:
        _consolidated_scores(services, viewer)


def _all_assignments(services, viewer: Viewer) -> None:
    assignments = services.scope.list_visible_assignments(viewer)
    if not assignments:
        st.write("No assignments yet.")
        return
    rows = [
        {
            "Agent": safe_get_name(services.party_repo, a.agent_id),
            "Manager": safe_get_name(services.party_repo, a.manager_id),
            "Start": a.start_date,
            "End": a.end_date,
            "State": a.state.value,
            "Closed reason": a.closed_reason or "",
        }
        for a in assignments
    ]
    with st.container(border=True):
        st.dataframe(rows, width='stretch')


def _org_structure(services, viewer: Viewer) -> None:
    """The whole current org: Functional Owner(s) -> Managers -> Agents.
    Shows every Manager and every Agent (even unassigned ones, as
    unconnected cards) so gaps in the structure are visible too — not
    just the active reporting lines, which come from active assignments
    only. An Agent with concurrent, cross-team assignments naturally gets
    more than one incoming edge; this is a graph, not a strict tree."""
    owners_parties = services.party_repo.list_by_type("functional_owner")
    manager_parties = services.party_repo.list_by_type("manager")
    agent_parties = services.party_repo.list_by_type("agent")

    if not manager_parties and not agent_parties:
        st.write("No org structure yet — onboard some people first.")
        return

    owners = [(f"o_{p.id.hex}", p.display_name) for p in owners_parties]
    managers = [(f"m_{p.id.hex}", p.display_name) for p in manager_parties]
    agents = [(f"a_{p.id.hex}", p.display_name) for p in agent_parties]

    edges_owner_manager = [
        (f"o_{o.id.hex}", f"m_{m.id.hex}") for o in owners_parties for m in manager_parties
    ]

    assignments = services.scope.list_visible_assignments(viewer)
    active = [a for a in assignments if a.state.value == "active"]
    edges_manager_agent = [
        (f"m_{a.manager_id.hex}", f"a_{a.agent_id.hex}") for a in active
    ]

    org_tree.render(owners, managers, agents, edges_owner_manager, edges_manager_agent)
    st.caption(
        "Showing current structure only (active assignments). "
        "Hover a card to trace its connections."
    )

    manager_counts: dict[str, int] = {}
    for a in active:
        key = f"a_{a.agent_id.hex}"
        manager_counts[key] = manager_counts.get(key, 0) + 1
    bifurcated_agent_ids = {
        a.agent_id for a in active if manager_counts.get(f"a_{a.agent_id.hex}", 0) > 1
    }
    if bifurcated_agent_ids:
        names = [safe_get_name(services.party_repo, agent_id) for agent_id in bifurcated_agent_ids]
        st.info("Currently reporting to more than one manager: " + ", ".join(names))


def _onboard_and_assign(services) -> None:
    st.caption("A two-step journey: bring people into the system, then connect them.")

    with st.container(border=True):
        st.markdown("**① Onboard people**")
        st.caption(
            "Email is optional today, but is the field a future SSO "
            "integration would match against — worth filling in now."
        )
        col1, col2 = st.columns(2)
        with col1:
            with st.form("new_agent"):
                name = st.text_input("New Agent name")
                email = st.text_input("Email (optional)", key="owner_agent_email")
                submitted = st.form_submit_button("Create Agent")
                if submitted and name:
                    attrs = {"email": email} if email else {}
                    services.party_repo.add(
                        Party(party_type="agent", display_name=name, attributes=attrs)
                    )
                    st.success(f"Agent '{name}' created.")
                    st.rerun()
        with col2:
            with st.form("new_manager"):
                name = st.text_input("New Manager name", key="manager_name")
                email = st.text_input("Email (optional)", key="owner_manager_email")
                submitted = st.form_submit_button("Create Manager")
                if submitted and name:
                    attrs = {"email": email} if email else {}
                    services.party_repo.add(
                        Party(party_type="manager", display_name=name, attributes=attrs)
                    )
                    st.success(f"Manager '{name}' created.")
                    st.rerun()

    with st.container(border=True):
        st.markdown("**② Create an assignment**")
        agents = services.party_repo.list_by_type("agent")
        managers = services.party_repo.list_by_type("manager")
        if not agents or not managers:
            st.info("Create at least one Agent and one Manager first.")
            return

        agent_labels = disambiguate_labels(agents)
        manager_labels = disambiguate_labels(managers)

        with st.form("new_assignment"):
            agent_choice = st.selectbox("Agent", list(agent_labels.keys()))
            manager_choice = st.selectbox("Manager", list(manager_labels.keys()))
            start = st.date_input("Start date", value=date.today())
            has_end = st.checkbox("Set an end date now")
            end = st.date_input("End date", value=date.today()) if has_end else None
            submitted = st.form_submit_button("Create Assignment")
            if submitted:
                try:
                    services.assignment_service.create_assignment(
                        agent_id=agent_labels[agent_choice].id,
                        manager_id=manager_labels[manager_choice].id,
                        start_date=start,
                        end_date=end,
                    )
                    st.success("Assignment created.")
                    st.rerun()
                except DuplicateAssignment:
                    st.error(
                        "This Agent already has an active assignment with this "
                        "Manager — close it first, or pick a different Manager."
                    )
                except ValueError as e:
                    st.error(str(e))


def _overdue(services, viewer: Viewer) -> None:
    st.subheader("Overdue goal setting")
    days = st.number_input("Overdue threshold (days)", min_value=1, value=14)
    overdue_goals = services.scope.list_overdue_goal_setting(viewer, older_than_days=int(days))
    if not overdue_goals:
        st.write("Nothing overdue.")
    else:
        rows = [
            {
                "Agent": safe_get_name(services.party_repo, a.agent_id),
                "Manager": safe_get_name(services.party_repo, a.manager_id),
                "Start": a.start_date,
            }
            for a in overdue_goals
        ]
        st.dataframe(rows, width='stretch')

    st.divider()
    st.subheader("Overdue closure")
    st.caption("Managers who are well past the point they could have closed and haven't.")
    overdue_closure = services.scope.list_overdue_closure(viewer)
    if not overdue_closure:
        st.write("Nothing overdue.")
    else:
        rows = [
            {
                "Agent": safe_get_name(services.party_repo, a.agent_id),
                "Manager": safe_get_name(services.party_repo, a.manager_id),
                "Start": a.start_date,
            }
            for a in overdue_closure
        ]
        st.dataframe(rows, width='stretch')

    st.caption(
        "Notification dispatch (block 7) isn't built yet — these are the "
        "queries a reminder job would poll."
    )


def _manager_handoff(services, viewer: Viewer) -> None:
    st.caption(
        "For when a Manager leaves: close every one of their active "
        "Assignments (no score — this isn't a performance assessment) "
        "and hand each Agent to a new Manager in one action."
    )
    managers = services.party_repo.list_by_type("manager")
    if len(managers) < 2:
        st.info("Need at least two Managers for a handoff.")
        return

    manager_labels = disambiguate_labels(managers)
    with st.form("manager_handoff"):
        departing_label = st.selectbox("Departing manager", list(manager_labels.keys()))
        remaining = {
            label: p
            for label, p in manager_labels.items()
            if p.id != manager_labels[departing_label].id
        }
        new_label = st.selectbox("New manager for their team", list(remaining.keys()))
        notes = st.text_area("Notes (optional)")
        submitted = st.form_submit_button("Reassign their whole team")

    if submitted:
        departing = manager_labels[departing_label]
        active_count = len(
            [a for a in services.scope.list_visible_assignments(viewer) if a.manager_id == departing.id and a.state.value == "active"]
        )
        if active_count == 0:
            st.info(f"{departing.display_name} has no active Agents to reassign.")
        else:
            new_assignments = services.scope.reassign_all_from_departing_manager(
                viewer, departing.id, remaining[new_label].id, notes=notes or None
            )
            st.success(f"Reassigned {len(new_assignments)} Agent(s).")
            st.rerun()


def _consolidated_scores(services, viewer: Viewer) -> None:
    agents = services.party_repo.list_by_type("agent")
    if not agents:
        st.write("No agents yet.")
        return
    labels = disambiguate_labels(agents)
    choice = st.selectbox("Agent", list(labels.keys()))
    agent = labels[choice]
    score = services.scope.consolidated_score(viewer, agent.id)
    if score is None:
        st.write("No closed assignments yet for this agent.")
    else:
        st.metric("Consolidated score", f"{score:.2f}")
