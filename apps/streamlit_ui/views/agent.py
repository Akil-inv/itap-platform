"""Associate's own view — "My Journey" — Phase 4 of the redesign
(docs/associate_journey_redesign.md's "Associate flow" section). Mostly
self-service and read access to the associate's own history, per spec:
a self-editable profile, their own aggregate score + per-episode
milestones (visible to no one else), the current episode's goal text
(editable pre-freeze, locked once the manager freezes it — the missing
half of Phase 3's Goals tab, which only wired the manager's side of the
same `GoalSetting` record), informational annual leave with no approval
workflow, and Teams/CCA interest flagging worded as a standing signal,
never a placement request.

Four tabs keep this one busy page organized, same "tabs on a page" idiom
as `views/manager_associate.py` / `views/associate_portfolio.py`, even
though this is a top-level page rather than a level-2 drill-down (there
is nowhere else for the associate to go — everything here is their own):

- **Profile** — bio, photo, experience, project highlights, skills.
  Self-added skills are always recorded with `SkillSource.SELF` (no
  verification step, per spec); engagement-sourced skills still only
  ever come from the admin/manager side (Phase 2/3 pages) — this page
  never lets an associate claim an engagement-sourced entry for
  themselves.
- **My Progress** — the rotation plan preview (unchanged from before
  this pass), own aggregate score (`ScopedAssignmentQueries.
  consolidated_score`, which already refuses anyone but the owning
  Agent), and a milestones view of past episode scores.
- **Current Episode(s)** — one expander per visible Assignment
  (Episode), same journey stepper as before; the Goal Setting block is
  now an editable form pre-freeze (writes to the same `GoalSetting`
  record via `AssignmentService.record_goal_setting` that the manager's
  Goals tab reads and freezes) and a locked, read-only view once
  `frozen` is true.
- **Leave & Interests** — annual leave date-range entries
  (`CatalogService.declare_leave`/`list_leave`, no approval workflow)
  and Teams/CCA interest flag toggles
  (`CatalogService.flag_interest`/`unflag_interest`), copy-checked to
  read as a signal, not a move request.
"""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st
from assignment.domain import GoalSettingFrozen
from assignment.rules import TransitionDenied
from catalog.domain import (
    AssociateProfile,
    ExperienceEntry,
    InterestTargetType,
    ProjectHighlight,
    SkillSource,
)
from party_identity.domain import Party
from rbac_scope import Viewer

import journey_curve
import score_curve
from journey import render_stepper, stage_index
from party_helpers import safe_get_name
from person_row import avatar_html


def render(services, viewer: Viewer, current_party: Party) -> None:
    st.title("My Journey")
    st.caption(f"Welcome back, {current_party.display_name}.")

    tab_profile, tab_progress, tab_episodes, tab_leave = st.tabs(
        ["Profile", "My Progress", "Current Episode(s)", "Leave & Interests"]
    )

    with tab_profile:
        _profile_tab(services, current_party)
    with tab_progress:
        _progress_tab(services, viewer, current_party)
    with tab_episodes:
        _episodes_tab(services, viewer)
    with tab_leave:
        _leave_and_interests_tab(services, current_party)


# --- Profile (self-editable, never frozen) ---------------------------------


def _profile_tab(services, current_party: Party) -> None:
    st.caption(
        "Fully self-editable at any time — this page is never frozen for "
        "the duration of your stay. An admin can also update your photo "
        "on your behalf if you're slow to do it yourself."
    )
    profile = services.catalog_service.get_profile(current_party.id)

    header_cols = st.columns([1, 5])
    with header_cols[0]:
        st.markdown(
            avatar_html(current_party.display_name, profile.photo_url if profile else None, large=True),
            unsafe_allow_html=True,
        )
    with header_cols[1]:
        st.subheader(current_party.display_name)
        st.caption("Associate")

    with st.form("agent_profile_form"):
        bio = st.text_area("Bio", value=profile.bio if profile else "")
        photo_url = st.text_input(
            "Photo URL", value=(profile.photo_url if profile else "") or ""
        )
        if st.form_submit_button("Save profile"):
            updated = AssociateProfile(
                agent_id=current_party.id,
                bio=bio,
                photo_url=photo_url or None,
                experience=list(profile.experience) if profile else [],
                project_highlights=list(profile.project_highlights) if profile else [],
            )
            services.catalog_service.update_profile(updated)
            st.success("Profile saved.")
            st.rerun()

    st.divider()
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
    with st.expander("Add an experience entry"):
        with st.form("agent_add_experience"):
            title = st.text_input("Title", key="agent_exp_title")
            description = st.text_area("Description", key="agent_exp_desc")
            if st.form_submit_button("Add") and title:
                base = profile or AssociateProfile(agent_id=current_party.id)
                base.experience = list(base.experience) + [
                    ExperienceEntry(title=title, description=description)
                ]
                services.catalog_service.update_profile(base)
                st.rerun()

    st.subheader("Project highlights")
    if profile and profile.project_highlights:
        for h in profile.project_highlights:
            st.markdown(f"- **{h.title}**" + (f" — {h.description}" if h.description else ""))
    else:
        st.caption("No project highlights yet.")
    with st.expander("Add a project highlight"):
        with st.form("agent_add_highlight"):
            title = st.text_input("Title", key="agent_hl_title")
            description = st.text_area("Description", key="agent_hl_desc")
            if st.form_submit_button("Add") and title:
                base = profile or AssociateProfile(agent_id=current_party.id)
                base.project_highlights = list(base.project_highlights) + [
                    ProjectHighlight(title=title, description=description)
                ]
                services.catalog_service.update_profile(base)
                st.rerun()

    st.subheader("Skills")
    st.caption(
        "Add certifications and new skills as you go — no verification "
        "step. Self-added and engagement-scored skills sit in the same "
        "list, distinguished only by a quiet source label."
    )
    associate_skills = services.catalog_service.list_associate_skills(current_party.id)
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

    with st.expander("Add a skill"):
        skills = services.catalog_service.list_skills()
        if not skills:
            st.info("No skills in the catalog yet — ask an admin to add one on Setup.")
        else:
            skill_labels = {s.name: s for s in skills}
            with st.form("agent_add_skill"):
                skill_choice = st.selectbox("Skill", list(skill_labels.keys()))
                if st.form_submit_button("Add skill"):
                    services.catalog_service.declare_associate_skill(
                        current_party.id, skill_labels[skill_choice].id, SkillSource.SELF
                    )
                    st.success(f"Added '{skill_choice}' (self-added).")
                    st.rerun()


# --- My Progress: rotation plan, own score, milestones ----------------------


def _progress_tab(services, viewer: Viewer, current_party: Party) -> None:
    _rotation_plan_progress(services, current_party)
    st.divider()
    _own_score_and_milestones(services, viewer, current_party)


def _rotation_plan_progress(services, current_party: Party) -> None:
    enrollments = services.rotation_plan_repo.list_enrollments_for_agent(current_party.id)
    if not enrollments:
        st.caption("No rotation plan enrollment yet — nothing to preview here.")
        return
    for enrollment in enrollments:
        plan = services.rotation_plan_repo.get_plan(enrollment.plan_id)
        value = services.rotation_plan_service.progress_value(enrollment, plan)

        stage_subs: list[str | None] = []
        for stage_index_i in range(plan.stage_count):
            assignment_id = enrollment.stage_assignments.get(stage_index_i)
            if assignment_id is None:
                stage_subs.append(None)
                continue
            try:
                linked_assignment = services.assignment_repo.get(assignment_id)
                stage_subs.append(safe_get_name(services.party_repo, linked_assignment.manager_id))
            except Exception:
                stage_subs.append(None)

        with st.container(border=True):
            stage_name = plan.stage_names[enrollment.current_stage_index]
            st.markdown(f"**Your rotation plan — {plan.name}**")
            st.caption(
                f"Stage {enrollment.current_stage_index + 1} of {plan.stage_count} — "
                f"{stage_name}"
            )
            journey_curve.render(
                plan.stage_names, stage_subs=stage_subs, progress=value, height=260
            )


def _own_score_and_milestones(services, viewer: Viewer, current_party: Party) -> None:
    """Per spec: visible ONLY to the owning associate, never to another
    associate, and never rolled up for a manager. `consolidated_score`
    already enforces that (raises PermissionDenied for anyone but the
    Agent themselves or the Functional Owner) — this call is exactly the
    Agent asking about themselves, so it always succeeds here."""
    st.subheader("Your aggregate score")
    st.caption(
        "Visible only to you — this is the simple average across every "
        "episode of any kind, all-time, so you can tell whether your "
        "trend is helping or hurting your overall number."
    )
    score = services.scope.consolidated_score(viewer, current_party.id)
    if score is None:
        st.info("No closed episodes yet — nothing to average.")
    else:
        st.metric("Aggregate score", f"{score:.2f}")

    st.subheader("Score milestones")
    st.caption("Only visible to you — each closed episode's own score, in order.")
    milestones = _episode_milestones(services, viewer)
    if not milestones:
        st.caption("No scored episodes yet.")
        return

    curve_html = score_curve.render_html(
        [{"score": m["score"], "label": f"Ep. {i + 1}"} for i, m in enumerate(milestones)]
    )
    st.markdown(curve_html, unsafe_allow_html=True)
    for i, m in enumerate(milestones):
        st.write(
            f"- **Episode {i + 1}** — {m['kind']} with {m['manager']}, "
            f"closed {m['closed_on']}: **{m['score']:.1f}** / 5.0"
        )


def _episode_milestones(services, viewer: Viewer) -> list[dict]:
    """Every closed, scored episode for this Agent, oldest first — the
    per-episode milestones the spec asks for "along their own learning
    curve." A simple ordered list (rendered above as a bar chart plus
    text) conveys "score progression over past episodes" without needing
    to match the approved mockup's SVG curve pixel-for-pixel."""
    assignments = services.scope.list_visible_assignments(viewer)
    rows = []
    for a in assignments:
        if a.state.value != "closed" or a.closed_reason != "completed":
            continue
        closure = services.scope.get_closure_record(viewer, a.id)
        if closure is None:
            continue
        rows.append(
            {
                "score": closure.objective_score,
                "kind": a.kind.value.capitalize(),
                "manager": safe_get_name(services.party_repo, a.manager_id),
                "closed_on": a.end_date or a.start_date,
            }
        )
    rows.sort(key=lambda r: r["closed_on"])
    return rows


# --- Current Episode(s) ------------------------------------------------------


def _episodes_tab(services, viewer: Viewer) -> None:
    assignments = services.scope.list_visible_assignments(viewer)
    if not assignments:
        st.write("You have no episodes yet.")
        return

    for assignment in assignments:
        manager_name = safe_get_name(services.party_repo, assignment.manager_id)
        kind_label = assignment.kind.value.capitalize()
        with st.expander(
            f"{kind_label} — {manager_name} — {assignment.state.value} "
            f"({assignment.start_date} to {assignment.end_date or 'open'})",
            expanded=(assignment.state.value == "active"),
        ):
            _episode_detail(services, viewer, assignment)


def _episode_detail(services, viewer: Viewer, assignment) -> None:
    goal_setting = services.scope.get_goal_setting(viewer, assignment.id)
    stage = stage_index(assignment, goal_setting)
    render_stepper(stage)

    with st.container(border=True):
        st.markdown("**Goal Setting**")
        _goal_setting_block(services, assignment, goal_setting)

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


def _goal_setting_block(services, assignment, goal_setting) -> None:
    """The missing half of Phase 3's Goals tab: the associate fills in
    proposed goals for the active engagement here (per spec's "Associate
    flow" -> "Current assignment"), keying into the exact same
    `GoalSetting` record the manager's Goals tab (`views/
    manager_associate.py`) reads and freezes via `freeze_goal_setting`.
    Locked, read-only once `frozen` is true — only an admin-opened
    window (Phase 4's Approvals tab) can undo that."""
    if goal_setting is not None and goal_setting.frozen:
        st.success("Agreed and frozen — locked for both of you.")
        st.write(goal_setting.goals)
        if goal_setting.criteria:
            st.caption("Scoring criteria: " + ", ".join(goal_setting.criteria))
        return

    if goal_setting is not None:
        st.caption("Current draft (editable until your manager agrees & freezes it):")
        st.write(goal_setting.goals)
    else:
        st.caption("Your manager hasn't recorded goal setting yet — you can propose it here.")

    if assignment.state.value != "active":
        return

    with st.form(f"agent_goals_{assignment.id}"):
        goals = st.text_area(
            "Proposed goals (agreed with your manager, verbally, first)",
            value=goal_setting.goals if goal_setting else "",
        )
        if st.form_submit_button("Save"):
            if not goals.strip():
                st.error("Enter your proposed goal text first.")
            else:
                try:
                    services.assignment_service.record_goal_setting(
                        assignment.id, goals, criteria=goal_setting.criteria if goal_setting else None
                    )
                    st.success("Saved. Your manager still needs to Agree & Freeze it.")
                    st.rerun()
                except GoalSettingFrozen as e:
                    st.error(str(e))


# --- Leave & Interests --------------------------------------------------


def _leave_and_interests_tab(services, current_party: Party) -> None:
    _annual_leave_section(services, current_party)
    st.divider()
    _interest_flagging_section(services, current_party)


def _annual_leave_section(services, current_party: Party) -> None:
    st.subheader("Annual leave")
    st.caption(
        "Purely informational, for manager/admin planning purposes — "
        "**no approval workflow.** Declaring dates here doesn't need "
        "anyone to sign off."
    )
    leave_entries = services.catalog_service.list_leave(current_party.id)
    if leave_entries:
        for entry in sorted(leave_entries, key=lambda e: e.start_date):
            note = f" — {entry.note}" if entry.note else ""
            st.write(f"- {entry.start_date} to {entry.end_date}{note}")
    else:
        st.caption("No leave declared yet.")

    with st.form("agent_declare_leave"):
        cols = st.columns(2)
        start = cols[0].date_input("Start date", value=date.today())
        end = cols[1].date_input("End date", value=date.today() + timedelta(days=1))
        note = st.text_input("Note (optional)")
        if st.form_submit_button("Declare leave"):
            try:
                services.catalog_service.declare_leave(
                    current_party.id, start, end, note=note
                )
                st.success("Leave declared.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def _interest_flagging_section(services, current_party: Party) -> None:
    st.subheader("Flag interest")
    st.caption(
        "A **general interest signal only** — not a request or "
        "preference to move. Flagging a Team or CCA here doesn't let "
        "you choose your next placement; it just tells the central team "
        "you'd welcome a conversation about it, if one makes sense."
    )

    active_flags = services.catalog_service.list_interests(current_party.id)
    flagged_team_ids = {
        f.target_id: f.id for f in active_flags if f.target_type == InterestTargetType.TEAM
    }
    flagged_cca_ids = {
        f.target_id: f.id for f in active_flags if f.target_type == InterestTargetType.CCA
    }

    st.markdown("**Teams**")
    teams = services.catalog_service.list_teams()
    if not teams:
        st.caption("No teams in the catalog yet.")
    for team in teams:
        cols = st.columns([3, 1])
        with cols[0]:
            manager_name = safe_get_name(services.party_repo, team.manager_id)
            flagged = team.id in flagged_team_ids
            st.write(f"{'✅ ' if flagged else ''}**{team.name}** _(led by {manager_name})_")
        with cols[1]:
            if flagged:
                if st.button(f"Remove interest: {team.name}", key=f"unflag_team_{team.id}"):
                    services.catalog_service.unflag_interest(
                        current_party.id, flagged_team_ids[team.id]
                    )
                    st.rerun()
            else:
                if st.button(f"Flag interest: {team.name}", key=f"flag_team_{team.id}"):
                    services.catalog_service.flag_interest(
                        current_party.id, InterestTargetType.TEAM, team.id
                    )
                    st.rerun()

    st.markdown("**CCA activities**")
    ccas = services.catalog_service.list_cca_activities()
    if not ccas:
        st.caption("No CCA activities in the catalog yet.")
    for cca in ccas:
        cols = st.columns([3, 1])
        with cols[0]:
            flagged = cca.id in flagged_cca_ids
            st.write(f"{'✅ ' if flagged else ''}**{cca.name}** _({cca.status.value})_")
        with cols[1]:
            if flagged:
                if st.button(f"Remove interest: {cca.name}", key=f"unflag_cca_{cca.id}"):
                    services.catalog_service.unflag_interest(
                        current_party.id, flagged_cca_ids[cca.id]
                    )
                    st.rerun()
            else:
                if st.button(f"Flag interest: {cca.name}", key=f"flag_cca_{cca.id}"):
                    services.catalog_service.flag_interest(
                        current_party.id, InterestTargetType.CCA, cca.id
                    )
                    st.rerun()
