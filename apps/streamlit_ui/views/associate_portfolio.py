"""Associate Portfolio — level 2 of the redesign
(docs/associate_journey_redesign.md): one page per Associate instead of
scattered tabs. Reached by clicking a name on the admin's Associates
list (views/functional_owner.py._associates_list). Combines: profile,
the Primary-spine rotation timeline (each stage's "N responsibilities"
badge expandable to Secondary/CCA detail), declared interest flags
(read-only), and the actions that used to live in separate top-level
tabs — close-and-advance, add a Secondary, log a CCA.

Admin-only for this phase (Phase 2) — manager/associate portfolio views
are a later phase per the task scope.
"""
from __future__ import annotations

import streamlit as st
from assignment.clock import today as clock_today
from assignment.domain import AssignmentKind, DuplicateAssignment
from catalog.domain import InterestTargetType, SkillSource
from party_helpers import disambiguate_labels, safe_get_name
from person_row import avatar_html


def render(services, viewer, agent) -> None:
    if st.button("← Back to Associates"):
        del st.session_state["selected_associate_id"]
        st.rerun()

    # Per spec: opening the profile is what clears the interest-change
    # highlight badge on the admin's list.
    services.catalog_service.mark_interest_seen(agent.id)

    all_assignments = services.assignment_repo.list_by_agent(agent.id)
    profile = services.catalog_service.get_profile(agent.id)

    header_cols = st.columns([1, 5])
    with header_cols[0]:
        st.markdown(avatar_html(agent.display_name, profile.photo_url if profile else None, large=True), unsafe_allow_html=True)
    with header_cols[1]:
        st.title(agent.display_name)
        email = agent.attributes.get("email")
        st.caption(f"Associate{' · ' + email if email else ''}")

    tab_profile, tab_timeline, tab_interests, tab_actions = st.tabs(
        ["Profile", "Rotation timeline", "Interest flags", "Actions"]
    )

    with tab_profile:
        _profile_section(services, agent, profile)
    with tab_timeline:
        _timeline_section(services, agent, all_assignments)
    with tab_interests:
        _interests_section(services, agent)
    with tab_actions:
        _actions_section(services, viewer, agent, all_assignments)


# --- Profile -----------------------------------------------------------


def _profile_section(services, agent, profile) -> None:
    st.subheader("Bio & experience")
    st.caption(
        "Sourced from Excel wherever possible; never frozen — editable here "
        "on the Associate's behalf at any time, same as the Associate can "
        "edit their own copy."
    )
    with st.form(f"profile_{agent.id}"):
        bio = st.text_area("Bio", value=profile.bio if profile else "")
        uploaded_photo = st.file_uploader(
            "Update photo", type=["png", "jpg", "jpeg", "gif", "webp"]
        )
        if st.form_submit_button("Save profile"):
            import photo_storage
            from catalog.domain import AssociateProfile

            photo_url = profile.photo_url if profile else None
            if uploaded_photo is not None:
                photo_url = photo_storage.save_photo(
                    agent.id, uploaded_photo.name, uploaded_photo.getvalue()
                )
            updated = AssociateProfile(
                agent_id=agent.id,
                bio=bio,
                photo_url=photo_url,
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
    with st.expander("Add an experience entry"), st.form(f"add_experience_{agent.id}"):
        title = st.text_input("Title")
        description = st.text_area("Description", key=f"exp_desc_{agent.id}")
        if st.form_submit_button("Add") and title:
            from catalog.domain import AssociateProfile, ExperienceEntry

            base = profile or AssociateProfile(agent_id=agent.id)
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
    with st.expander("Add a project highlight"), st.form(f"add_highlight_{agent.id}"):
        title = st.text_input("Title", key=f"hl_title_{agent.id}")
        description = st.text_area("Description", key=f"hl_desc_{agent.id}")
        if st.form_submit_button("Add") and title:
            from catalog.domain import AssociateProfile, ProjectHighlight

            base = profile or AssociateProfile(agent_id=agent.id)
            base.project_highlights = list(base.project_highlights) + [
                ProjectHighlight(title=title, description=description)
            ]
            services.catalog_service.update_profile(base)
            st.rerun()

    st.subheader("Skills")
    st.caption(
        "Self-declared and engagement-scored skills sit in the same list, "
        "distinguished only by a quiet source label — no verification/"
        "approval step, per spec."
    )
    associate_skills = services.catalog_service.list_associate_skills(agent.id)
    all_skills = {s.id: s for s in services.catalog_service.list_skills()}
    if associate_skills:
        for a_skill in associate_skills:
            skill = all_skills.get(a_skill.skill_id)
            if skill is None:
                continue
            label = "self-added" if a_skill.source == SkillSource.SELF else a_skill.source_detail or "from an engagement"
            st.markdown(f"- **{skill.name}** _({label})_")
    else:
        st.caption("No skills declared yet.")

    with st.expander("Add a skill"):
        skills = services.catalog_service.list_skills()
        if not skills:
            st.info("No skills in the catalog yet — add one on the Setup page first.")
        else:
            skill_labels = {s.name: s for s in skills}
            with st.form(f"add_skill_{agent.id}"):
                skill_choice = st.selectbox("Skill", list(skill_labels.keys()))
                source_choice = st.radio(
                    "Source", ["Self-declared", "From an engagement"], horizontal=True
                )
                detail = st.text_input(
                    "Detail (e.g. \"Data Team engagement, Mar 2026\")",
                    disabled=(source_choice == "Self-declared"),
                )
                if st.form_submit_button("Add skill"):
                    source = (
                        SkillSource.SELF if source_choice == "Self-declared" else SkillSource.ENGAGEMENT
                    )
                    services.catalog_service.declare_associate_skill(
                        agent.id, skill_labels[skill_choice].id, source, source_detail=detail
                    )
                    st.rerun()


# --- Rotation timeline ---------------------------------------------------


def _overlapping(all_assignments, stage_start, stage_end):
    """Secondary/CCA assignments anchored to this Primary stage per the
    spec's overlap rule: anchored to whichever Primary stage was active
    on the episode's *start date*. `stage_end` is None for the current
    (open-ended) stage."""
    out = []
    for a in all_assignments:
        if a.kind == AssignmentKind.PRIMARY:
            continue
        if a.start_date < stage_start:
            continue
        if stage_end is not None and a.start_date >= stage_end:
            continue
        out.append(a)
    return out


def _timeline_section(services, agent, all_assignments) -> None:
    import journey_curve
    from battery import primary_assignments

    primaries = primary_assignments(all_assignments)
    if not primaries:
        st.info("No Primary assignment yet — this Associate hasn't started a rotation.")
        return

    st.subheader("Rotation timeline")

    # Overview: the same winding "journey curve" the Rotation Plan preview
    # uses (journey_curve.py) — one visual language for "a journey" across
    # the whole app, not a straight stepper here and a curve elsewhere.
    team_name_by_manager = {
        t.manager_id: t.name for t in services.catalog_service.list_teams()
    }
    stage_names, stage_subs = [], []
    for p in primaries:
        manager_name = safe_get_name(services.party_repo, p.manager_id)
        stage_names.append(team_name_by_manager.get(p.manager_id, manager_name))
        stage_subs.append(f"{p.start_date} – {p.end_date or 'open'}")
    active_index = next(
        (i for i, p in enumerate(primaries) if p.state.value == "active"),
        len(primaries) - 1,
    )
    journey_curve.render(stage_names, stage_subs=stage_subs, progress=float(active_index), height=260)

    for i, primary in enumerate(primaries):
        is_active = primary.state.value == "active"
        stage_end = None if is_active else primary.end_date
        next_start = primaries[i + 1].start_date if i + 1 < len(primaries) else None
        overlap_end = next_start if next_start else stage_end
        overlapping = _overlapping(all_assignments, primary.start_date, overlap_end)
        responsibilities = [primary] + overlapping
        manager_name = safe_get_name(services.party_repo, primary.manager_id)

        css_class = "itap-stage-active" if is_active else ""
        st.markdown(
            f'<div class="itap-stage-card {css_class}">'
            f"<strong>{'Current: ' if is_active else ''}{manager_name}</strong> "
            f"({primary.start_date} – {primary.end_date or 'open'})"
            f"</div>",
            unsafe_allow_html=True,
        )
        with st.expander(f"{len(responsibilities)} responsibilities"):
            for r in responsibilities:
                _responsibility_row(services, r)

    # A gap after the last Primary closed, with nothing new started yet.
    last = primaries[-1]
    if last.state.value == "closed":
        overlapping = _overlapping(all_assignments, last.end_date or last.start_date, None)
        if overlapping:
            st.markdown('<div class="itap-stage-card itap-stage-gap">Available (gap)</div>', unsafe_allow_html=True)
            with st.expander(f"{len(overlapping)} responsibilities during this gap"):
                for r in overlapping:
                    _responsibility_row(services, r)


def _responsibility_row(services, assignment) -> None:
    manager_name = safe_get_name(services.party_repo, assignment.manager_id)
    kind_label = assignment.kind.value.capitalize()
    score_text = ""
    if assignment.state.value == "closed" and assignment.closed_reason == "completed":
        closure = services.assignment_repo.get_closure_record(assignment.id)
        if closure:
            score_text = f" — score {closure.objective_score:.1f}"
    st.write(
        f"**{kind_label}** · {manager_name} · "
        f"{assignment.start_date} to {assignment.end_date or 'open'}{score_text}"
    )


# --- Interest flags -------------------------------------------------------


def _interests_section(services, agent) -> None:
    st.caption(
        "A general standing interest signal, not a request or preference "
        "to move — placement decisions are made separately by the "
        "central team and managers."
    )
    flags = services.catalog_service.list_interests(agent.id)
    if not flags:
        st.write("No interests flagged yet.")
        return
    teams = {t.id: t.name for t in services.catalog_service.list_teams()}
    ccas = {c.id: c.name for c in services.catalog_service.list_cca_activities()}
    for f in flags:
        if f.target_type == InterestTargetType.TEAM:
            name = teams.get(f.target_id, "Unknown team")
            st.write(f"- Team: **{name}**")
        else:
            name = ccas.get(f.target_id, "Unknown CCA")
            st.write(f"- CCA: **{name}**")


# --- Actions ---------------------------------------------------------------


def _actions_section(services, viewer, agent, all_assignments) -> None:
    from battery import current_primary, primary_assignments

    primaries = primary_assignments(all_assignments)
    active_primary = current_primary(primaries)
    managers = services.party_repo.list_by_type("manager")
    manager_labels = disambiguate_labels(managers)

    st.subheader("Close current Primary & advance")
    if active_primary is None:
        st.caption("No active Primary assignment to close.")
    else:
        with st.form(f"close_advance_{agent.id}"):
            score = st.slider("Objective score", 0.0, 5.0, 3.0, 0.1)
            notes = st.text_area("Subjective notes")
            advance_now = st.checkbox("Start the next Primary stage now")
            next_manager_label = None
            if advance_now and manager_labels:
                next_manager_label = st.selectbox(
                    "Next manager", list(manager_labels.keys()), key=f"next_mgr_{agent.id}"
                )
            if st.form_submit_button("Close & advance"):
                try:
                    services.assignment_service.close_assignment(
                        active_primary.id, objective_score=score, subjective_notes=notes
                    )
                    import rotation_plan_bridge

                    rotation_plan_bridge.advance_linked_stage_if_closed(services, active_primary.id)
                    if advance_now and next_manager_label:
                        services.assignment_service.create_assignment(
                            agent_id=agent.id,
                            manager_id=manager_labels[next_manager_label].id,
                            start_date=clock_today(),
                            kind=AssignmentKind.PRIMARY,
                        )
                    st.success("Closed" + (" and advanced." if advance_now else "."))
                    st.rerun()
                except (ValueError, DuplicateAssignment) as e:
                    st.error(str(e))

    st.divider()
    st.subheader("Add a Secondary assignment")
    st.caption("A real, concurrent assignment under a different manager.")
    if not manager_labels:
        st.info("Onboard at least one Manager first.")
    else:
        with st.form(f"add_secondary_{agent.id}"):
            manager_choice = st.selectbox("Manager", list(manager_labels.keys()), key=f"sec_mgr_{agent.id}")
            start = st.date_input("Start date", value=clock_today(), key=f"sec_start_{agent.id}")
            if st.form_submit_button("Add Secondary"):
                try:
                    services.assignment_service.create_assignment(
                        agent_id=agent.id,
                        manager_id=manager_labels[manager_choice].id,
                        start_date=start,
                        kind=AssignmentKind.SECONDARY,
                    )
                    st.success("Secondary assignment created.")
                    st.rerun()
                except (ValueError, DuplicateAssignment) as e:
                    st.error(str(e))

    st.divider()
    st.subheader("Log a CCA")
    ccas = services.catalog_service.list_cca_activities()
    if not ccas:
        st.info("No CCA activities in the catalog yet — add one on the Setup page first.")
    else:
        cca_labels = {c.name: c for c in ccas}
        with st.form(f"log_cca_{agent.id}"):
            cca_choice = st.selectbox("CCA activity", list(cca_labels.keys()))
            start = st.date_input("Start date", value=clock_today(), key=f"cca_start_{agent.id}")
            if st.form_submit_button("Log CCA"):
                cca = cca_labels[cca_choice]
                try:
                    services.assignment_service.create_assignment(
                        agent_id=agent.id,
                        manager_id=cca.organizer_manager_id,
                        start_date=start,
                        kind=AssignmentKind.CCA,
                    )
                    st.success("CCA logged.")
                    st.rerun()
                except (ValueError, DuplicateAssignment) as e:
                    st.error(str(e))
