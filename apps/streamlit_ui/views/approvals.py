"""Admin approvals — Phase 4 of the redesign, closing the gap Phase 3
explicitly deferred (see docs/architecture.md's Phase 3 "Deferred"
note): a place for the Functional Owner to act on manager-raised
`ChangeRequest`s (Extension/Closure) and to reopen a frozen
`GoalSetting`/`ReviewScore` for a specific Assignment.

**Judgment call — its own top-level tab, not folded into Setup**: Setup
(`views/setup.py`) is explicitly "not mixed into daily operational
screens" per the spec — Skills/Teams/CCA catalogs are the kind of thing
an admin configures once and revisits occasionally. Approvals is the
opposite: a queue of day-to-day, per-associate/per-manager actions an
admin works through regularly, same "different rate of change" cutoff
the architecture doc uses elsewhere to justify a boundary. It reads much
closer to the Associates list or Overdue tab than to Setup, so it gets
its own tab next to those instead.

Two sections:

- **Pending requests** — every PENDING `ChangeRequest`
  (`AssignmentService.list_pending_change_requests`), each with the
  Associate/Manager names, the request detail, and Approve/Deny buttons
  (`approve_change_request`/`deny_change_request`). Approving a CLOSURE
  request is what actually applies the assignment's frozen `ReviewScore`
  and closes it — same as the underlying service call already documents.
- **Reopen a frozen Goal Setting or Review Score** — pick any Assignment
  (active or closed), see whether its `GoalSetting`/`ReviewScore` is
  currently frozen, and reopen either one
  (`reopen_goal_setting`/`reopen_review_score`). This is what turns the
  manager's disabled "(admin only)" stub buttons on `views/
  manager_associate.py` into something with a real landing spot.
"""
from __future__ import annotations

import rotation_plan_bridge
import streamlit as st
from assignment.domain import AssignmentNotFound, RequestType
from party_helpers import safe_get_name


def render(services, viewer) -> None:
    st.title("Approvals")
    st.caption(
        "Manager-raised Extension/Closure requests, and admin reopen "
        "actions for a frozen Goal Setting or Review Score."
    )

    st.subheader("Pending requests")
    _pending_requests_section(services, viewer)

    st.divider()
    st.subheader("Reopen a frozen Goal Setting or Review Score")
    st.caption(
        "Per spec: if a manager wants to add a new project to the "
        "measurement mid-engagement, or correct a submitted score, an "
        "admin must open the window first — there's no self-service "
        "edit path around the freeze for either side."
    )
    _reopen_section(services)


# --- Pending change requests -------------------------------------------


def _pending_requests_section(services, viewer) -> None:
    requests = services.assignment_service.list_pending_change_requests()
    if not requests:
        st.write("No pending requests.")
        return

    for request in sorted(requests, key=lambda r: r.requested_at):
        try:
            assignment = services.assignment_repo.get(request.assignment_id)
        except AssignmentNotFound:
            continue
        agent_name = safe_get_name(services.party_repo, assignment.agent_id)
        manager_name = safe_get_name(services.party_repo, assignment.manager_id)
        label = request.request_type.value.capitalize()
        detail = (
            f" → new end date {request.new_end_date}"
            if request.request_type == RequestType.EXTENSION and request.new_end_date
            else ""
        )

        with st.container(border=True):
            st.markdown(f"**{label} request**{detail}")
            st.caption(
                f"{agent_name} · {manager_name} · requested {request.requested_at:%Y-%m-%d}"
            )
            if request.notes:
                st.write(request.notes)

            cols = st.columns(2)
            with cols[0]:
                if st.button("Approve", key=f"approve_{request.id}", type="primary"):
                    try:
                        services.assignment_service.approve_change_request(
                            request.id, decided_by=viewer.party_id
                        )
                        if request.request_type == RequestType.CLOSURE:
                            rotation_plan_bridge.advance_linked_stage_if_closed(
                                services, request.assignment_id
                            )
                        st.success(f"{label} request approved.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            with cols[1], st.popover("Deny"), st.form(f"deny_form_{request.id}"):
                deny_notes = st.text_area("Reason (optional)", key=f"deny_notes_{request.id}")
                if st.form_submit_button("Confirm deny"):
                    try:
                        services.assignment_service.deny_change_request(
                            request.id, decided_by=viewer.party_id, notes=deny_notes or None
                        )
                        st.success(f"{label} request denied.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))


# --- Reopen frozen Goals / Review Score ----------------------------------


def _reopen_section(services) -> None:
    assignments = services.assignment_repo.list_all()

    # Only list assignments that actually have something frozen to
    # reopen — picking blind from every assignment in the system (most
    # of which have nothing frozen) was the exact confusion a real admin
    # ran into: the dropdown gave no way to tell which one was the right
    # one without already knowing, so a wrong guess just read "not
    # frozen" with no hint of where to look instead.
    frozen = []
    for a in assignments:
        goal_setting = services.assignment_repo.get_goal_setting(a.id)
        review_score = services.assignment_repo.get_review_score(a.id)
        goal_frozen = goal_setting is not None and goal_setting.frozen
        score_frozen = review_score is not None and review_score.frozen
        if goal_frozen or score_frozen:
            frozen.append((a, goal_frozen, score_frozen))

    if not frozen:
        st.write("Nothing is currently frozen — no assignment needs reopening.")
        return

    labels = {}
    for a, goal_frozen, score_frozen in sorted(frozen, key=lambda t: t[0].start_date, reverse=True):
        agent_name = safe_get_name(services.party_repo, a.agent_id)
        manager_name = safe_get_name(services.party_repo, a.manager_id)
        frozen_what = " & ".join(
            filter(None, ["goals" if goal_frozen else None, "score" if score_frozen else None])
        )
        label = (
            f"{agent_name} → {manager_name} ({a.kind.value}, {a.state.value}) — "
            f"{frozen_what} frozen · {str(a.id)[:8]}"
        )
        labels[label] = a

    choice = st.selectbox("Assignment", list(labels.keys()), key="reopen_assignment_choice")
    assignment = labels[choice]

    goal_setting = services.assignment_repo.get_goal_setting(assignment.id)
    review_score = services.assignment_repo.get_review_score(assignment.id)

    cols = st.columns(2)
    with cols[0]:
        st.markdown("**Goal Setting**")
        if goal_setting is None:
            st.caption("No goal setting recorded for this assignment.")
        elif not goal_setting.frozen:
            st.caption("Not frozen — nothing to reopen.")
        else:
            st.write(goal_setting.goals)
            if st.button("Reopen Goal Setting", key=f"reopen_goals_{assignment.id}"):
                try:
                    services.assignment_service.reopen_goal_setting(assignment.id)
                    st.success("Goal setting reopened — the manager/associate can edit it again.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
    with cols[1]:
        st.markdown("**Review Score**")
        if review_score is None:
            st.caption("No review score recorded for this assignment.")
        elif not review_score.frozen:
            st.caption("Not frozen — nothing to reopen.")
        else:
            st.write(f"Objective score: {review_score.objective_score:.2f}")
            if st.button("Reopen Review Score", key=f"reopen_score_{assignment.id}"):
                try:
                    services.assignment_service.reopen_review_score(assignment.id)
                    st.success("Review score reopened — the manager can correct and resubmit.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
