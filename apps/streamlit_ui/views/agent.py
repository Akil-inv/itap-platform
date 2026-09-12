from __future__ import annotations

import streamlit as st
from assignment.rules import TransitionDenied
from party_identity.domain import Party
from rbac_scope import Viewer

from journey import render_stepper, stage_index
from party_helpers import safe_get_name


def render(services, viewer: Viewer, current_party: Party) -> None:
    st.title("My Journey")
    st.caption(f"Welcome back, {current_party.display_name}.")

    assignments = services.scope.list_visible_assignments(viewer)
    if not assignments:
        st.write("You have no assignments yet.")
        return

    for assignment in assignments:
        manager_name = safe_get_name(services.party_repo, assignment.manager_id)
        with st.expander(
            f"{manager_name} — {assignment.state.value} "
            f"({assignment.start_date} to {assignment.end_date or 'open'})",
            expanded=(assignment.state.value == "active"),
        ):
            _assignment_journey(services, viewer, assignment)


def _assignment_journey(services, viewer: Viewer, assignment) -> None:
    goal_setting = services.scope.get_goal_setting(viewer, assignment.id)
    stage = stage_index(assignment, goal_setting)
    render_stepper(stage)

    with st.container(border=True):
        st.markdown("**Goal Setting**")
        if goal_setting is None:
            st.caption("Your manager hasn't recorded goal setting yet.")
        else:
            st.write(goal_setting.goals)
            if goal_setting.criteria:
                st.caption("Scoring criteria: " + ", ".join(goal_setting.criteria))

    closure = services.scope.get_closure_record(viewer, assignment.id)
    with st.container(border=True):
        st.markdown("**Your score**")
        if assignment.state.value == "closed" and assignment.closed_reason != "completed":
            reason_label = (assignment.closed_reason or "closed").replace("_", " ")
            st.caption(f"Closed — {reason_label}, not scored.")
        elif closure:
            st.write(f"{closure.objective_score} — {closure.subjective_notes}")
        else:
            st.caption("Not yet scored.")

    with st.container(border=True):
        st.markdown("**Give feedback about your manager**")
        with st.form(f"feedback_{assignment.id}"):
            notes = st.text_area("Your feedback")
            if st.form_submit_button("Submit feedback") and notes:
                try:
                    services.assignment_service.record_reverse_feedback(assignment.id, notes)
                    st.success("Feedback recorded.")
                    st.rerun()
                except TransitionDenied as e:
                    st.error(str(e))

        existing = services.scope.list_reverse_feedback(viewer, assignment.id)
        if existing:
            st.caption("Feedback you've already given:")
            for f in existing:
                st.write(f"- {f.notes} _(recorded {f.recorded_at:%Y-%m-%d})_")
