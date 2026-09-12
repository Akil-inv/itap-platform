from __future__ import annotations

from datetime import date

import streamlit as st
from party_identity.domain import Party
from rbac_scope import Viewer

from party_helpers import party_label, safe_get_name


def render(services, viewer: Viewer) -> None:
    st.title("Functional Owner")

    tabs = st.tabs(["All Assignments", "Onboard & Assign", "Overdue Goal Setting", "Consolidated Scores"])

    with tabs[0]:
        _all_assignments(services, viewer)
    with tabs[1]:
        _onboard_and_assign(services)
    with tabs[2]:
        _overdue_goal_setting(services, viewer)
    with tabs[3]:
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
    st.dataframe(rows, width='stretch')


def _onboard_and_assign(services) -> None:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Onboard a new Agent")
        with st.form("new_agent"):
            name = st.text_input("Agent name")
            submitted = st.form_submit_button("Create Agent")
            if submitted and name:
                services.party_repo.add(Party(party_type="agent", display_name=name))
                st.success(f"Agent '{name}' created.")
                st.rerun()

        st.subheader("Onboard a new Manager")
        with st.form("new_manager"):
            name = st.text_input("Manager name", key="manager_name")
            submitted = st.form_submit_button("Create Manager")
            if submitted and name:
                services.party_repo.add(Party(party_type="manager", display_name=name))
                st.success(f"Manager '{name}' created.")
                st.rerun()

    with col2:
        st.subheader("Assign an Agent to a Manager")
        agents = services.party_repo.list_by_type("agent")
        managers = services.party_repo.list_by_type("manager")
        if not agents or not managers:
            st.info("Create at least one Agent and one Manager first.")
            return

        agent_labels = {party_label(p): p for p in agents}
        manager_labels = {party_label(p): p for p in managers}

        with st.form("new_assignment"):
            agent_choice = st.selectbox("Agent", list(agent_labels.keys()))
            manager_choice = st.selectbox("Manager", list(manager_labels.keys()))
            start = st.date_input("Start date", value=date.today())
            has_end = st.checkbox("Set an end date now")
            end = st.date_input("End date", value=date.today()) if has_end else None
            submitted = st.form_submit_button("Create Assignment")
            if submitted:
                services.assignment_service.create_assignment(
                    agent_id=agent_labels[agent_choice].id,
                    manager_id=manager_labels[manager_choice].id,
                    start_date=start,
                    end_date=end,
                )
                st.success("Assignment created.")
                st.rerun()


def _overdue_goal_setting(services, viewer: Viewer) -> None:
    days = st.number_input("Overdue threshold (days)", min_value=1, value=14)
    overdue = services.scope.list_overdue_goal_setting(viewer, older_than_days=int(days))
    if not overdue:
        st.write("Nothing overdue.")
        return
    rows = [
        {
            "Agent": safe_get_name(services.party_repo, a.agent_id),
            "Manager": safe_get_name(services.party_repo, a.manager_id),
            "Start": a.start_date,
        }
        for a in overdue
    ]
    st.dataframe(rows, width='stretch')
    st.caption(
        "Notification dispatch (block 7) isn't built yet — this is the "
        "query a reminder job would poll."
    )


def _consolidated_scores(services, viewer: Viewer) -> None:
    agents = services.party_repo.list_by_type("agent")
    if not agents:
        st.write("No agents yet.")
        return
    labels = {party_label(p): p for p in agents}
    choice = st.selectbox("Agent", list(labels.keys()))
    agent = labels[choice]
    score = services.scope.consolidated_score(viewer, agent.id)
    if score is None:
        st.write("No closed assignments yet for this agent.")
    else:
        st.metric("Consolidated score", f"{score:.2f}")
