from __future__ import annotations

from datetime import date

import streamlit as st
from assignment.domain import ConcurrentModification
from assignment.rules import TransitionDenied
from party_identity.domain import Party
from rbac_scope import PermissionDenied, Viewer

import rotation_plan_bridge
from journey import render_stepper, stage_index
from party_helpers import safe_get_name

ACTIONABLE_ERRORS = (TransitionDenied, ConcurrentModification)


def render(services, viewer: Viewer, current_party: Party) -> None:
    st.title("My Team")
    st.caption(f"Welcome back, {current_party.display_name}.")

    assignments = services.scope.list_visible_assignments(viewer)
    if not assignments:
        st.write("No Agents currently tasked to you.")
        return

    for assignment in assignments:
        agent_name = safe_get_name(services.party_repo, assignment.agent_id)
        with st.expander(
            f"{agent_name} — {assignment.state.value} "
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
            st.warning("No goal setting recorded yet — nothing to assess against at closure.")
            with st.form(f"goals_{assignment.id}"):
                goals = st.text_area("Goals (agreed with the agent)")
                criteria_text = st.text_input(
                    "Scoring criteria (semicolon-separated, optional)",
                    placeholder="Communication; Technical Skill; Ownership",
                )
                if st.form_submit_button("Record goal setting") and goals:
                    criteria = [c.strip() for c in criteria_text.split(";") if c.strip()]
                    services.assignment_service.record_goal_setting(
                        assignment.id, goals, criteria=criteria
                    )
                    st.rerun()
        else:
            st.write(goal_setting.goals)
            if goal_setting.criteria:
                st.caption("Scoring criteria: " + ", ".join(goal_setting.criteria))

    if assignment.state.value == "active":
        with st.container(border=True):
            st.markdown("**Assignment in progress**")
            tab_extend, tab_close, tab_withdraw = st.tabs(
                ["Request extension", "Close assignment", "Withdraw"]
            )

            with tab_extend:
                with st.form(f"extend_{assignment.id}"):
                    new_end = st.date_input(
                        "New end date", value=assignment.end_date or date.today()
                    )
                    if st.form_submit_button("Request extension"):
                        try:
                            services.assignment_service.request_extension(
                                assignment.id,
                                requested_by=viewer.party_id,
                                new_end_date=new_end,
                            )
                            st.success("Extended.")
                            st.rerun()
                        except ACTIONABLE_ERRORS as e:
                            st.error(str(e))

            with tab_close:
                if goal_setting is None:
                    st.info("Record goal setting above first — there's nothing to close against yet.")
                with st.form(f"close_{assignment.id}"):
                    score = st.slider("Objective score", 0.0, 5.0, 3.0, 0.1)
                    notes = st.text_area("Subjective notes")
                    if st.form_submit_button("Close assignment"):
                        try:
                            services.assignment_service.close_assignment(
                                assignment.id, objective_score=score, subjective_notes=notes
                            )
                            rotation_plan_bridge.advance_linked_stage_if_closed(
                                services, assignment.id
                            )
                            st.success("Closed.")
                            st.rerun()
                        except ACTIONABLE_ERRORS as e:
                            st.error(str(e))

            with tab_withdraw:
                st.caption(
                    "For when the Agent leaves the program or this rotation early — "
                    "no score is recorded, this isn't a performance assessment."
                )
                with st.form(f"withdraw_{assignment.id}"):
                    notes = st.text_area("Reason (optional)", key=f"withdraw_notes_{assignment.id}")
                    if st.form_submit_button("Withdraw this assignment"):
                        try:
                            services.assignment_service.withdraw_assignment(
                                assignment.id, notes=notes or None
                            )
                            rotation_plan_bridge.advance_linked_stage_if_closed(
                                services, assignment.id
                            )
                            st.success("Withdrawn.")
                            st.rerun()
                        except ACTIONABLE_ERRORS as e:
                            st.error(str(e))
    else:
        with st.container(border=True):
            st.markdown("**Closed**")
            if assignment.closed_reason == "completed":
                closure = services.scope.get_closure_record(viewer, assignment.id)
                if closure:
                    st.write(f"**Score:** {closure.objective_score} — {closure.subjective_notes}")
            else:
                reason_label = (assignment.closed_reason or "closed").replace("_", " ")
                st.write(f"**Reason:** {reason_label}")
                if assignment.closure_note:
                    st.write(assignment.closure_note)

    with st.container(border=True):
        st.markdown("**Feedback from this Agent about you**")
        try:
            feedback = services.scope.list_reverse_feedback(viewer, assignment.id)
        except PermissionDenied:
            feedback = []
        if feedback:
            for f in feedback:
                st.write(f"- {f.notes} _(recorded {f.recorded_at:%Y-%m-%d})_")
        else:
            st.caption("No feedback recorded yet.")
