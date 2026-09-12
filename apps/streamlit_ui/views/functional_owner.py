from __future__ import annotations

from datetime import date

import streamlit as st
from party_identity.domain import Party
from rbac_scope import Viewer

from party_helpers import party_label, safe_get_name


def render(services, viewer: Viewer) -> None:
    st.title("Functional Owner")

    tabs = st.tabs(
        [
            "All Assignments",
            "Org Structure",
            "Onboard & Assign",
            "Overdue Goal Setting",
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
        _overdue_goal_setting(services, viewer)
    with tabs[4]:
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


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _org_structure(services, viewer: Viewer) -> None:
    """Manager -> Agent graph. Deliberately a graph, not a strict tree —
    an Agent with concurrent, cross-team assignments has more than one
    incoming edge, and that's the case this view exists to surface."""
    assignments = services.scope.list_visible_assignments(viewer)
    if not assignments:
        st.write("No assignments yet.")
        return

    lines = ["digraph OrgStructure {", "rankdir=LR;", 'node [fontname="Helvetica"];']
    seen_nodes: set[str] = set()
    manager_counts: dict[str, int] = {}

    for a in assignments:
        # DOT identifiers can't contain hyphens unless quoted; UUIDs are
        # hyphenated, so use .hex (no hyphens) for the node id itself —
        # the human-readable name still goes in the label.
        manager_node = f"m_{a.manager_id.hex}"
        agent_node = f"a_{a.agent_id.hex}"

        if manager_node not in seen_nodes:
            name = _dot_escape(safe_get_name(services.party_repo, a.manager_id))
            lines.append(
                f'{manager_node} [label="{name}", shape=box, style=filled, '
                f'fillcolor="#EAF1FA", color="#4C78A8"];'
            )
            seen_nodes.add(manager_node)

        if agent_node not in seen_nodes:
            name = _dot_escape(safe_get_name(services.party_repo, a.agent_id))
            lines.append(
                f'{agent_node} [label="{name}", shape=ellipse, style=filled, '
                f'fillcolor="#ECF7EA", color="#54A24B"];'
            )
            seen_nodes.add(agent_node)

        active = a.state.value == "active"
        style = "solid" if active else "dashed"
        lines.append(f'{manager_node} -> {agent_node} [label="{a.state.value}", style={style}];')

        if active:
            manager_counts[agent_node] = manager_counts.get(agent_node, 0) + 1

    lines.append("}")
    st.graphviz_chart("\n".join(lines))
    st.caption("Solid edge = active assignment. Dashed edge = closed.")

    bifurcated_agent_ids = {
        a.agent_id for a in assignments if manager_counts.get(f"a_{a.agent_id.hex}", 0) > 1
    }
    if bifurcated_agent_ids:
        names = [safe_get_name(services.party_repo, agent_id) for agent_id in bifurcated_agent_ids]
        st.info("Currently reporting to more than one manager: " + ", ".join(names))


def _onboard_and_assign(services) -> None:
    st.caption("A two-step journey: bring people into the system, then connect them.")

    with st.container(border=True):
        st.markdown("**① Onboard people**")
        col1, col2 = st.columns(2)
        with col1:
            with st.form("new_agent"):
                name = st.text_input("New Agent name")
                submitted = st.form_submit_button("Create Agent")
                if submitted and name:
                    services.party_repo.add(Party(party_type="agent", display_name=name))
                    st.success(f"Agent '{name}' created.")
                    st.rerun()
        with col2:
            with st.form("new_manager"):
                name = st.text_input("New Manager name", key="manager_name")
                submitted = st.form_submit_button("Create Manager")
                if submitted and name:
                    services.party_repo.add(Party(party_type="manager", display_name=name))
                    st.success(f"Manager '{name}' created.")
                    st.rerun()

    with st.container(border=True):
        st.markdown("**② Create an assignment**")
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
