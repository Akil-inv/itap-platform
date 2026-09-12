"""Manager's own view of one Associate — level 2 of the redesign, Phase 3
(docs/associate_journey_redesign.md's "Manager flow" -> "Associate
profile" section). Reached by clicking a name on `views/manager.py`'s
Current/Rolled Off list, same "level 2 page via session_state, not a
nested tab" pattern as `views/functional_owner.py` ->
`views/associate_portfolio.py`.

Three tabs, matching the approved mockup's structure exactly:

- **Profile** — read-only catalog profile (no edit affordance here; the
  associate's own page, a later phase, owns editing per spec).
- **Goals** — the associate's own page doesn't exist yet, so this tab is
  the stand-in: the manager views/edits the *current engagement's* goal
  text directly and clicks **Agree & Freeze**
  (`AssignmentService.freeze_goal_setting`), which locks it for both
  sides. Only an admin-opened window can undo that — see the "Admin
  reopen" stub note below.
- **Review & Scoring** — score entry against the engagement's criteria
  (`AssignmentService.submit_review_score`, simple average, frozen
  immediately on submit), then the direct **Withdraw** action
  (no approval) plus the two new gated **Request Extension** / **Request
  Closure** actions (`AssignmentService.request_change` — creates a
  PENDING `ChangeRequest`, does not itself extend or close anything; the
  admin-approval screen that acts on these is explicitly out of scope
  for this pass, see docs/architecture.md's Phase 3 section).

**"Current engagement" — judgment call**: the spec's mockup shows one
Goals/Review & Scoring tab per Associate page, but the domain allows a
Manager to hold more than one concurrent Assignment with the same
Associate (e.g. a Primary plus a CCA they personally organize). Rather
than silently picking one, an engagement selector appears whenever this
Manager has more than one ACTIVE Assignment with this Associate; with
exactly one it's chosen silently (no pointless selector for the common
case). Rolled-off/closed engagements show a read-only summary instead —
Goals/Review & Scoring only ever act on an *active* engagement.
"""
from __future__ import annotations

from assignment.domain import (
    ChangeRequestNotFound,
    ConcurrentModification,
    GoalSettingFrozen,
    RequestType,
    ReviewScoreFrozen,
)
from assignment.rules import TransitionDenied

import streamlit as st

ACTIONABLE_ERRORS = (
    ValueError,
    TransitionDenied,
    ConcurrentModification,
    GoalSettingFrozen,
    ReviewScoreFrozen,
    ChangeRequestNotFound,
)


def render(services, viewer, agent) -> None:
    if st.button("← Back to My Team"):
        del st.session_state["selected_manager_associate_id"]
        st.rerun()

    my_assignments = [
        a
        for a in services.assignment_repo.list_by_agent(agent.id)
        if a.manager_id == viewer.party_id
    ]
    active = sorted(
        (a for a in my_assignments if a.state.value == "active"), key=lambda a: a.start_date
    )
    closed = sorted(
        (a for a in my_assignments if a.state.value != "active"),
        key=lambda a: a.start_date,
        reverse=True,
    )

    header_cols = st.columns([1, 5])
    with header_cols[0]:
        profile = services.catalog_service.get_profile(agent.id)
        if profile and profile.photo_url:
            st.image(profile.photo_url, width=88)
        else:
            st.markdown(
                '<div style="width:72px;height:72px;border-radius:50%;'
                'background:#EAF1F8;display:flex;align-items:center;'
                'justify-content:center;font-size:1.6rem;font-weight:700;'
                'color:#333F6B;">' + agent.display_name[:1].upper() + "</div>",
                unsafe_allow_html=True,
            )
    with header_cols[1]:
        st.title(agent.display_name)
        st.caption("Associate")

    tab_profile, tab_goals, tab_review = st.tabs(["Profile", "Goals", "Review & Scoring"])

    with tab_profile:
        _profile_section(services, agent)

    engagement = _select_engagement(active, key_prefix="goals")
    with tab_goals:
        if engagement is None:
            _no_active_engagement(closed)
        else:
            _goals_section(services, viewer, engagement)

    engagement2 = _select_engagement(active, key_prefix="review")
    with tab_review:
        if engagement2 is None:
            _no_active_engagement(closed)
        else:
            _review_scoring_section(services, viewer, engagement2)


# --- Profile (read-only) --------------------------------------------------


def _profile_section(services, agent) -> None:
    profile = services.catalog_service.get_profile(agent.id)
    st.caption("Read-only — the Associate's own profile page (a later phase) owns editing.")

    st.subheader("Bio")
    st.write(profile.bio if profile and profile.bio else "No bio recorded yet.")

    st.subheader("Experience")
    if profile and profile.experience:
        for e in profile.experience:
            span = ""
            if e.start_date or e.end_date:
                span = f" ({e.start_date or '?'} – {e.end_date or 'present'})"
            st.markdown(f"**{e.title}**{span}")
            if e.description:
                st.caption(e.description)
    else:
        st.caption("No prior experience entries yet.")

    st.subheader("Project highlights")
    if profile and profile.project_highlights:
        for h in profile.project_highlights:
            st.markdown(f"- **{h.title}**" + (f" — {h.description}" if h.description else ""))
    else:
        st.caption("No project highlights yet.")

    st.subheader("Skills")
    from catalog.domain import SkillSource

    associate_skills = services.catalog_service.list_associate_skills(agent.id)
    all_skills = {s.id: s for s in services.catalog_service.list_skills()}
    if associate_skills:
        for a_skill in associate_skills:
            skill = all_skills.get(a_skill.skill_id)
            if skill is None:
                continue
            label = (
                "self-added"
                if a_skill.source == SkillSource.SELF
                else a_skill.source_detail or "from an engagement"
            )
            st.markdown(f"- **{skill.name}** _({label})_")
    else:
        st.caption("No skills declared yet.")


# --- Engagement selection --------------------------------------------------


def _select_engagement(active, key_prefix: str):
    if not active:
        return None
    if len(active) == 1:
        return active[0]
    labels = {
        f"{a.kind.value.capitalize()} — started {a.start_date}": a for a in active
    }
    choice = st.selectbox(
        "Engagement", list(labels.keys()), key=f"{key_prefix}_engagement_choice_{active[0].agent_id}"
    )
    return labels[choice]


def _no_active_engagement(closed) -> None:
    if closed:
        st.info(
            "No active engagement with you right now — this Associate's most "
            "recent engagement with you has closed. See the Rolled Off tab "
            "on My Team for read-only history."
        )
    else:
        st.info("No engagement with you yet.")


# --- Goals -----------------------------------------------------------------


def _goals_section(services, viewer, assignment) -> None:
    st.caption(
        "The manager and associate agree on goals verbally, offline; key "
        "the agreed goals in here, then click **Agree & Freeze** — once "
        "frozen, neither side can edit them without an admin reopening "
        "the window."
    )
    goal_setting = services.assignment_repo.get_goal_setting(assignment.id)

    if goal_setting is not None and goal_setting.frozen:
        st.success("Goals are agreed and frozen.")
        st.write(goal_setting.goals)
        if goal_setting.criteria:
            st.caption("Scoring criteria: " + ", ".join(goal_setting.criteria))
        st.caption(
            f"Agreed at {goal_setting.agreed_at:%Y-%m-%d %H:%M} UTC."
            if goal_setting.agreed_at
            else "Agreed."
        )
        st.button(
            "Reopen for editing (admin only)",
            disabled=True,
            key=f"reopen_goals_stub_{assignment.id}",
            help=(
                "TODO: not wired in this pass — an admin-approval screen "
                "would call AssignmentService.reopen_goal_setting. See "
                "docs/architecture.md's Phase 3 section."
            ),
        )
        return

    with st.form(f"goals_{assignment.id}"):
        goals = st.text_area(
            "Goals (agreed with the associate)",
            value=goal_setting.goals if goal_setting else "",
        )
        criteria_text = st.text_input(
            "Scoring criteria (semicolon-separated)",
            value=", ".join(goal_setting.criteria).replace(", ", "; ") if goal_setting and goal_setting.criteria else "",
            placeholder="Communication; Technical Skill; Ownership",
        )
        cols = st.columns(2)
        save_clicked = cols[0].form_submit_button("Save")
        freeze_clicked = cols[1].form_submit_button("Agree & Freeze", type="primary")
        if save_clicked or freeze_clicked:
            if not goals.strip():
                st.error("Enter the agreed goal text first.")
            else:
                criteria = [c.strip() for c in criteria_text.split(";") if c.strip()]
                try:
                    services.assignment_service.record_goal_setting(
                        assignment.id, goals, criteria=criteria
                    )
                    if freeze_clicked:
                        services.assignment_service.freeze_goal_setting(
                            assignment.id, agreed_by=viewer.party_id
                        )
                        st.success("Goals agreed and frozen.")
                    else:
                        st.success("Saved.")
                    st.rerun()
                except ACTIONABLE_ERRORS as e:
                    st.error(str(e))


# --- Review & Scoring --------------------------------------------------


def _review_scoring_section(services, viewer, assignment) -> None:
    goal_setting = services.assignment_repo.get_goal_setting(assignment.id)
    review_score = services.assignment_repo.get_review_score(assignment.id)

    if goal_setting is None or not goal_setting.frozen:
        st.info("Agree & Freeze the goals on the Goals tab first — there's nothing to score against yet.")
        criteria = None
    else:
        criteria = goal_setting.criteria or ["Overall"]

    if criteria is None:
        pass
    elif review_score is not None and review_score.frozen:
        st.success(f"Score submitted — objective score **{review_score.objective_score:.2f}** / 5.0")
        for name, value in review_score.criterion_scores.items():
            st.write(f"- {name}: {value:.1f}")
        if review_score.notes:
            st.caption(review_score.notes)
        st.button(
            "Reopen for correction (admin only)",
            disabled=True,
            key=f"reopen_score_stub_{assignment.id}",
            help=(
                "TODO: not wired in this pass — an admin-approval screen "
                "would call AssignmentService.reopen_review_score. See "
                "docs/architecture.md's Phase 3 section."
            ),
        )
    else:
        st.caption(
            "Score directly against each agreed criterion — no admin gate on "
            "this step. The objective score is the simple average across "
            "criteria, computed automatically. Frozen immediately on submit."
        )
        with st.form(f"score_{assignment.id}"):
            criterion_scores = {}
            for c in criteria:
                criterion_scores[c] = st.slider(c, 0.0, 5.0, 3.0, 0.1, key=f"score_{assignment.id}_{c}")
            notes = st.text_area("Notes")
            if st.form_submit_button("Submit score", type="primary"):
                try:
                    services.assignment_service.submit_review_score(
                        assignment.id, criterion_scores, notes, submitted_by=viewer.party_id
                    )
                    st.success("Score submitted and frozen.")
                    st.rerun()
                except ACTIONABLE_ERRORS as e:
                    st.error(str(e))

    st.divider()
    _pending_requests(services, assignment)

    st.divider()
    st.subheader("Withdraw")
    st.caption(
        "Direct action, no admin approval — for early/exceptional exits "
        "from a rotation or the program. No score is recorded."
    )
    with st.form(f"withdraw_{assignment.id}"):
        withdraw_notes = st.text_area("Reason (optional)", key=f"withdraw_notes_{assignment.id}")
        if st.form_submit_button("Withdraw this engagement", type="secondary"):
            try:
                services.assignment_service.withdraw_assignment(
                    assignment.id, notes=withdraw_notes or None
                )
                import rotation_plan_bridge

                rotation_plan_bridge.advance_linked_stage_if_closed(services, assignment.id)
                st.success("Withdrawn.")
                st.rerun()
            except ACTIONABLE_ERRORS as e:
                st.error(str(e))

    st.divider()
    st.subheader("Request Extension or Closure")
    st.caption(
        "Unlike Withdraw, these are **requests** — an admin must approve "
        "before anything changes. The admin-approval screen is not built "
        "yet (see docs/architecture.md's Phase 3 section); this is the "
        "request-creation half only."
    )
    req_cols = st.columns(2)
    with req_cols[0]:
        with st.form(f"request_extension_{assignment.id}"):
            from datetime import date, timedelta

            floor = assignment.end_date or assignment.start_date
            new_end = st.date_input(
                "New end date", value=floor + timedelta(days=90), min_value=floor + timedelta(days=1)
            )
            if st.form_submit_button("Request Extension"):
                try:
                    services.assignment_service.request_change(
                        assignment.id,
                        request_type=RequestType.EXTENSION,
                        requested_by=viewer.party_id,
                        new_end_date=new_end,
                    )
                    st.success("Extension requested — pending admin approval.")
                    st.rerun()
                except ACTIONABLE_ERRORS as e:
                    st.error(str(e))
    with req_cols[1]:
        with st.form(f"request_closure_{assignment.id}"):
            closure_notes = st.text_area("Notes (optional)", key=f"closure_notes_{assignment.id}")
            if st.form_submit_button("Request Closure"):
                try:
                    services.assignment_service.request_change(
                        assignment.id,
                        request_type=RequestType.CLOSURE,
                        requested_by=viewer.party_id,
                        notes=closure_notes,
                    )
                    st.success("Closure requested — pending admin approval.")
                    st.rerun()
                except ACTIONABLE_ERRORS as e:
                    st.error(str(e))


def _pending_requests(services, assignment) -> None:
    requests = services.assignment_service.list_change_requests(assignment.id)
    if not requests:
        return
    st.subheader("Requests on this engagement")
    for r in sorted(requests, key=lambda r: r.requested_at, reverse=True):
        label = r.request_type.value.capitalize()
        status = r.status.value.capitalize()
        detail = f" → {r.new_end_date}" if r.request_type == RequestType.EXTENSION and r.new_end_date else ""
        st.write(f"- **{label}**{detail} — {status} (requested {r.requested_at:%Y-%m-%d})")
