from __future__ import annotations

from datetime import date
from uuid import UUID

import streamlit as st
from assignment.domain import DuplicateAssignment
from party_identity.domain import Party
from rbac_scope import Viewer

import bulk_import
import journey_curve
import org_tree
import rotation_plan_bridge
from catalog.domain import UploadKind
from associate_status import AssociateStatus, classify, current_team_label
from battery import render_html as render_battery_html
from party_helpers import disambiguate_labels, safe_get_name
from person_row import render_person_row
from rotation_plan.domain import AlreadyEnrolled, RotationPlanNotFound
from views import approvals as approvals_view
from views import associate_portfolio
from views import setup as setup_view
from tokens import TOKENS

# Distinct marker colors for plotting several Associates on one shared
# rotation-plan curve — reuses the same battery past-stint palette
# (plus the primary/brand color) rather than a separate, ad hoc list.
_MARKER_COLORS = [TOKENS.semantic["success"], *TOKENS.battery["past_palette"]]


def render(services, viewer: Viewer, current_party: Party) -> None:
    # Associate Portfolio is a level-2 page (per the redesign spec), not
    # another top-level tab — reached by clicking a name in the
    # Associates list below, and left by its own "Back" button. It gets
    # its own title instead of "Workforce Overview" above it.
    selected_id = st.session_state.get("selected_associate_id")
    if selected_id is not None:
        try:
            agent = services.party_repo.get(UUID(selected_id))
        except Exception:
            del st.session_state["selected_associate_id"]
            st.rerun()
            return
        associate_portfolio.render(services, viewer, agent)
        return

    st.title("Workforce Overview")
    st.caption(f"Welcome back, {current_party.display_name}.")

    tabs = st.tabs(
        [
            "Associates",
            "Org Structure",
            "Onboard & Assign",
            "Setup",
            "Approvals",
            "Rotation Plans",
            "Bulk Setup",
            "Overdue",
            "Manager Handoff",
            "Consolidated Scores",
        ]
    )

    with tabs[0]:
        _associates_list(services, viewer)
    with tabs[1]:
        _org_structure(services, viewer)
    with tabs[2]:
        _onboard_and_assign(services)
    with tabs[3]:
        setup_view.render(services)
    with tabs[4]:
        approvals_view.render(services, viewer)
    with tabs[5]:
        _rotation_plans(services)
    with tabs[6]:
        _bulk_setup(services, current_party)
    with tabs[7]:
        _overdue(services, viewer)
    with tabs[8]:
        _manager_handoff(services, viewer)
    with tabs[9]:
        _consolidated_scores(services, viewer)


def _associates_list(services, viewer: Viewer) -> None:
    """The redesign's entry point (docs/associate_journey_redesign.md,
    "Associates list"): one row per Associate, replacing the old flat
    "All Assignments" table. Shows current team, a tenure battery bar,
    a hidden aggregate score behind a reveal, an interest-change
    highlight, and status filter chips."""
    agents = services.party_repo.list_by_type("agent")
    if not agents:
        st.write("No Associates yet.")
        return

    overdue_ids = {
        a.id for a in services.scope.list_overdue_goal_setting(viewer, older_than_days=14)
    } | {a.id for a in services.scope.list_overdue_closure(viewer)}

    rows = []
    for agent in sorted(agents, key=lambda p: p.display_name):
        all_assignments = services.assignment_repo.list_by_agent(agent.id)
        status = classify(all_assignments, overdue_ids)
        rows.append((agent, all_assignments, status))

    status_options = ["All"] + [s.value for s in AssociateStatus]
    chosen = st.radio("Status", status_options, horizontal=True, key="associates_status_filter")
    if chosen != "All":
        rows = [r for r in rows if r[2].value == chosen]

    if not rows:
        st.write("No Associates match this filter.")
        return

    _STATUS_CSS_CLASS = {
        AssociateStatus.ACTIVE: "itap-status-active",
        AssociateStatus.NEEDS_ATTENTION: "itap-status-attention",
        AssociateStatus.AVAILABLE: "itap-status-available",
        AssociateStatus.COMPLETED: "itap-status-completed",
    }

    for agent, all_assignments, status in rows:
        highlighted = services.catalog_service.has_unseen_interest_change(agent.id)
        battery_html = render_battery_html(all_assignments)
        profile = services.catalog_service.get_profile(agent.id)
        clicked, extra_cols = render_person_row(
            key=f"assoc_{agent.id}",
            display_name=agent.display_name,
            photo_url=profile.photo_url if profile else None,
            sub_label=f"Current team: {current_team_label(services, all_assignments)}",
            battery_html=battery_html,
            extra_col_weights=[1.6, 0.8],
        )
        with extra_cols[0]:
            badge = (
                '<span class="itap-interest-badge">interest changed</span>' if highlighted else ""
            )
            st.markdown(
                f'<span class="itap-status-chip {_STATUS_CSS_CLASS[status]}">'
                f"{status.value}</span>{badge}",
                unsafe_allow_html=True,
            )
        with extra_cols[1]:
            # Bank-balance "reveal, then hide" — exactly one row's score
            # is ever revealed at a time (a single shared key in session
            # state, not a per-row flag), so opening a different row's
            # score closes whichever one was open, per the spec's
            # "never shown inline" rule: at rest every row shows a
            # closed-eye icon, never the number.
            revealed_id = st.session_state.get("revealed_score_agent_id")
            if revealed_id == str(agent.id):
                score = services.scope.consolidated_score(viewer, agent.id)
                score_text = f"{score:.2f}" if score is not None else "—"
                if st.button(
                    score_text,
                    key=f"score_hide_{agent.id}",
                    icon=":material/visibility:",
                    width="stretch",
                ):
                    st.session_state["revealed_score_agent_id"] = None
                    st.rerun()
            else:
                if st.button(
                    "",
                    key=f"score_show_{agent.id}",
                    icon=":material/visibility_off:",
                    width="stretch",
                ):
                    st.session_state["revealed_score_agent_id"] = str(agent.id)
                    st.rerun()
        if clicked:
            st.session_state["selected_associate_id"] = str(agent.id)
            st.rerun()

    st.divider()
    with st.expander("Raw assignment table (all kinds, all history)"):
        assignments = services.scope.list_visible_assignments(viewer)
        table_rows = [
            {
                "Associate": safe_get_name(services.party_repo, a.agent_id),
                "Manager": safe_get_name(services.party_repo, a.manager_id),
                "Kind": a.kind.value,
                "Start": a.start_date,
                "End": a.end_date,
                "State": a.state.value,
                "Closed reason": a.closed_reason or "",
            }
            for a in assignments
        ]
        st.dataframe(table_rows, width='stretch')


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

    photo_urls = {}
    for p in owners_parties + manager_parties + agent_parties:
        profile = services.catalog_service.get_profile(p.id)
        if profile and profile.photo_url:
            prefix = "o_" if p in owners_parties else ("m_" if p in manager_parties else "a_")
            photo_urls[f"{prefix}{p.id.hex}"] = profile.photo_url

    org_tree.render(
        owners, managers, agents, edges_owner_manager, edges_manager_agent, photo_urls=photo_urls
    )
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
                name = st.text_input("New Associate name")
                email = st.text_input("Email (optional)", key="owner_agent_email")
                submitted = st.form_submit_button("Create Associate")
                if submitted and name:
                    attrs = {"email": email} if email else {}
                    services.party_repo.add(
                        Party(party_type="agent", display_name=name, attributes=attrs)
                    )
                    st.success(f"Associate '{name}' created.")
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
            st.info("Create at least one Associate and one Manager first.")
            return

        agent_labels = disambiguate_labels(agents)
        manager_labels = disambiguate_labels(managers)

        with st.form("new_assignment"):
            agent_choice = st.selectbox("Associate", list(agent_labels.keys()))
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
                        "This Associate already has an active assignment with this "
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
                "Associate": safe_get_name(services.party_repo, a.agent_id),
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
                "Associate": safe_get_name(services.party_repo, a.agent_id),
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
        "and hand each Associate to a new Manager in one action."
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
        closing_ids = [
            a.id
            for a in services.scope.list_visible_assignments(viewer)
            if a.manager_id == departing.id and a.state.value == "active"
        ]
        if not closing_ids:
            st.info(f"{departing.display_name} has no active Associates to reassign.")
        else:
            new_assignments = services.scope.reassign_all_from_departing_manager(
                viewer, departing.id, remaining[new_label].id, notes=notes or None
            )
            for assignment_id in closing_ids:
                rotation_plan_bridge.advance_linked_stage_if_closed(services, assignment_id)
            st.success(f"Reassigned {len(new_assignments)} Associate(s).")
            st.rerun()


def _rotation_plans(services) -> None:
    st.caption(
        "A fixed, named path of stages an Associate rotates through — so "
        "their next placement isn't a one-off decision each time. "
        "Stages are tracks/labels (e.g. \"Data Team\"), not a specific "
        "Manager — the Manager for each stage still comes from a normal "
        "Assignment, created separately."
    )

    with st.expander("Create a rotation plan"):
        with st.form("new_rotation_plan"):
            name = st.text_input("Plan name", placeholder="Engineering Foundations Track")
            stages_raw = st.text_input(
                "Stages, in order (semicolon-separated)",
                placeholder="Platform Team; Data Team; Product Team",
            )
            weeks = st.number_input("Weeks per stage", min_value=1, value=8)
            if st.form_submit_button("Create plan") and name and stages_raw:
                stage_names = [s.strip() for s in stages_raw.split(";") if s.strip()]
                try:
                    services.rotation_plan_service.create_plan(
                        name=name, stage_names=stage_names, weeks_per_stage=int(weeks)
                    )
                    st.success(f"'{name}' created.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    plans = services.rotation_plan_repo.list_plans()
    if not plans:
        st.info("No rotation plans yet — create one above.")
        return

    plan_labels = {p.name: p for p in plans}
    with st.expander("Enroll an associate"):
        agents = services.party_repo.list_by_type("agent")
        if not agents:
            st.info("Onboard at least one Associate first.")
        else:
            agent_labels = disambiguate_labels(agents)
            with st.form("enroll_in_plan"):
                plan_choice = st.selectbox("Plan", list(plan_labels.keys()))
                agent_choice = st.selectbox("Associate", list(agent_labels.keys()))
                if st.form_submit_button("Enroll"):
                    try:
                        services.rotation_plan_service.enroll(
                            plan_labels[plan_choice].id, agent_labels[agent_choice].id
                        )
                        st.success(f"Enrolled {agent_choice} in '{plan_choice}'.")
                        st.rerun()
                    except AlreadyEnrolled:
                        st.error("This Associate is already enrolled in this plan.")

    managers = services.party_repo.list_by_type("manager")
    manager_labels = disambiguate_labels(managers)
    manager_label_by_id = {p.id: label for label, p in manager_labels.items()}
    NO_DEFAULT = "— none —"

    for plan in plans:
        enrollments = services.rotation_plan_repo.list_enrollments_for_plan(plan.id)
        with st.container(border=True):
            st.markdown(f"**{plan.name}** — {len(enrollments)} enrolled")
            st.caption(" → ".join(plan.stage_names) + f" · {plan.weeks_per_stage} weeks/stage")

            with st.expander("Default manager per stage (auto-creates the next Assignment)"):
                st.caption(
                    "When an Associate's stage advances — because the linked "
                    "Assignment closed — a stage with a default Manager "
                    "here gets a fresh Assignment created and linked "
                    "automatically. Leave a stage as \"none\" to keep "
                    "linking it by hand."
                )
                if not manager_labels:
                    st.info("Onboard at least one Manager first.")
                else:
                    with st.form(f"default_managers_{plan.id}"):
                        choices = {}
                        for i, stage_name in enumerate(plan.stage_names):
                            current = plan.default_stage_managers.get(i)
                            options = [NO_DEFAULT] + list(manager_labels.keys())
                            default_index = (
                                options.index(manager_label_by_id[current])
                                if current in manager_label_by_id
                                else 0
                            )
                            choices[i] = st.selectbox(
                                f"Stage {i + 1} — {stage_name}",
                                options,
                                index=default_index,
                                key=f"default_manager_{plan.id}_{i}",
                            )
                        if st.form_submit_button("Save default managers"):
                            for stage_index, choice in choices.items():
                                manager_id = (
                                    None if choice == NO_DEFAULT else manager_labels[choice].id
                                )
                                services.rotation_plan_service.set_default_manager(
                                    plan.id, stage_index, manager_id
                                )
                            st.success("Saved.")
                            st.rerun()

            if enrollments:
                markers = []
                rows = []
                for i, enrollment in enumerate(enrollments):
                    agent_name = safe_get_name(services.party_repo, enrollment.agent_id)
                    value = services.rotation_plan_service.progress_value(enrollment, plan)
                    color = _MARKER_COLORS[i % len(_MARKER_COLORS)]
                    markers.append(
                        {"initial": agent_name[:1].upper(), "value": value, "color": color}
                    )
                    stage_name = plan.stage_names[enrollment.current_stage_index]
                    is_last = enrollment.current_stage_index >= plan.stage_count - 1
                    rows.append((enrollment, agent_name, stage_name, is_last))

                journey_curve.render(plan.stage_names, markers=markers, height=260)

                for enrollment, agent_name, stage_name, is_last in rows:
                    linked_id = enrollment.current_assignment_id
                    linked_caption = "No Assignment linked to this stage yet."
                    if linked_id is not None:
                        try:
                            linked_assignment = services.assignment_repo.get(linked_id)
                            manager_name = safe_get_name(
                                services.party_repo, linked_assignment.manager_id
                            )
                            linked_caption = (
                                f"Covered by **{manager_name}** "
                                f"({linked_assignment.start_date} to "
                                f"{linked_assignment.end_date or 'open'})"
                            )
                        except Exception:
                            linked_caption = "The linked Assignment no longer exists."

                    header = (
                        f"{agent_name} — Stage {enrollment.current_stage_index + 1} of "
                        f"{plan.stage_count} ({stage_name})"
                    )
                    with st.expander(header):
                        st.caption(linked_caption)

                        active_assignments = [
                            a
                            for a in services.assignment_repo.list_by_agent(enrollment.agent_id)
                            if a.state.value == "active"
                        ]
                        if active_assignments:
                            assignment_labels = {
                                f"{safe_get_name(services.party_repo, a.manager_id)} "
                                f"(since {a.start_date})": a
                                for a in active_assignments
                            }
                            col_a, col_b = st.columns([3, 1])
                            with col_a:
                                assignment_choice = st.selectbox(
                                    "Link an active Assignment to this stage",
                                    list(assignment_labels.keys()),
                                    key=f"link_choice_{enrollment.id}",
                                )
                            with col_b:
                                st.write("")
                                st.write("")
                                if st.button("Link", key=f"link_btn_{enrollment.id}"):
                                    services.rotation_plan_service.link_assignment(
                                        enrollment.id,
                                        enrollment.current_stage_index,
                                        assignment_labels[assignment_choice].id,
                                    )
                                    st.rerun()
                        else:
                            st.caption(
                                "No active Assignment for this Associate to link yet — "
                                "create one in Onboard & Assign."
                            )

                        st.divider()
                        if not is_last:
                            if st.button("Advance to next stage", key=f"advance_{enrollment.id}"):
                                services.rotation_plan_service.advance_stage(enrollment.id)
                                st.rerun()
                        else:
                            st.caption("Final stage — nothing to advance to.")
            else:
                st.caption("No one enrolled yet.")


def _bulk_setup(services, current_party: Party) -> None:
    st.caption(
        "Upload a Setup Workbook to create or UPDATE Admins, Managers "
        "(+ Teams), Associates (+ profile/skills/interests), Skills, CCA "
        "Activities, and Assignments (open or already-finished/scored) — "
        "in one pass. Re-uploading the same workbook is always safe: each "
        "row is matched by its natural key (email for people; name for "
        "catalogs; associate+manager+kind+start_date for one assignment "
        "stint) and its fields are UPDATED to whatever the file now says — "
        "nothing is ever duplicated. Nothing is written until you review "
        "the preview and click Confirm."
    )

    # Show the previous import's result (if any) before anything else.
    # All tabs render in one script pass, in a fixed order — Org
    # Structure/All Assignments are computed BEFORE this tab runs, so an
    # import here can't retroactively update what already rendered
    # earlier in the same pass. A st.rerun() below forces a fresh pass
    # where every tab recomputes against the post-import data; stashing
    # the result in session_state first is what lets the "Import
    # complete" message survive that rerun instead of vanishing with it.
    pending_result = st.session_state.pop("bulk_import_result", None)
    if pending_result is not None:
        _render_import_result(pending_result)

    st.download_button(
        "Download template (.xlsx)",
        data=bulk_import.build_template_workbook(),
        file_name="itap_bulk_setup_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    with st.expander("Past uploads (audit log)"):
        _upload_history(services)

    uploaded = st.file_uploader("Upload filled-in workbook", type=["xlsx"])
    photos_zip = st.file_uploader(
        "Upload photos.zip (optional — matched by email or photo_filename)",
        type=["zip"],
    )
    if uploaded is None:
        st.session_state.pop("bulk_import_parsed", None)
        st.session_state.pop("bulk_import_cache_key", None)
        return

    cache_key = (uploaded.name, uploaded.size)
    if st.session_state.get("bulk_import_cache_key") != cache_key:
        try:
            parsed = bulk_import.parse_workbook(uploaded)
        except Exception as e:
            st.error(f"Could not read this file: {e}")
            return
        st.session_state["bulk_import_cache_key"] = cache_key
        st.session_state["bulk_import_parsed"] = parsed
        st.session_state["bulk_import_raw_bytes"] = uploaded.getvalue()
        st.session_state["bulk_import_filename"] = uploaded.name

    parsed = st.session_state["bulk_import_parsed"]

    if parsed.sheet_errors:
        st.error("This workbook doesn't match the expected template:")
        for e in parsed.sheet_errors:
            st.write(f"- {e}")
        return

    st.write(
        f"Found **{len(parsed.admins)}** Admin row(s), "
        f"**{len(parsed.associates)}** Associate row(s), "
        f"**{len(parsed.managers)}** Manager row(s), "
        f"**{len(parsed.assignments)}** Assignment row(s), "
        f"**{len(parsed.skills)}** Skill row(s), "
        f"**{len(parsed.cca_activities)}** CCA Activity row(s)."
    )
    with st.expander("Preview parsed rows", expanded=True):
        if parsed.admins:
            st.markdown("**Admins**")
            st.dataframe(parsed.admins, width='stretch')
        if parsed.associates:
            st.markdown("**Associates**")
            st.dataframe(parsed.associates, width='stretch')
        if parsed.managers:
            st.markdown("**Managers**")
            st.dataframe(parsed.managers, width='stretch')
        if parsed.assignments:
            st.markdown("**Assignments**")
            st.dataframe(parsed.assignments, width='stretch')
        if parsed.skills:
            st.markdown("**Skills**")
            st.dataframe(parsed.skills, width='stretch')
        if parsed.cca_activities:
            st.markdown("**CCA Activities**")
            st.dataframe(parsed.cca_activities, width='stretch')

    if st.button("Confirm and import", type="primary"):
        photos_bytes = photos_zip.getvalue() if photos_zip is not None else None
        result = bulk_import.apply_import(services, parsed, photos_zip=photos_bytes)
        counts = result.counts()
        errors = [r.message for r in result.row_results if r.status == "error"]
        services.catalog_service.log_upload(
            uploaded_by_name=current_party.display_name,
            kind=UploadKind.WORKBOOK,
            filename=st.session_state.get("bulk_import_filename", "workbook.xlsx"),
            raw_file=st.session_state.get("bulk_import_raw_bytes", b""),
            summary=counts,
            errors=errors,
            uploaded_by=current_party.id,
        )
        if photos_bytes is not None:
            services.catalog_service.log_upload(
                uploaded_by_name=current_party.display_name,
                kind=UploadKind.PHOTOS,
                filename=photos_zip.name,
                raw_file=photos_bytes,
                summary={"matched": sum(1 for r in result.row_results if "photo saved" in r.message)},
                errors=[],
                uploaded_by=current_party.id,
            )
        st.session_state.pop("bulk_import_parsed", None)
        st.session_state.pop("bulk_import_cache_key", None)
        st.session_state.pop("bulk_import_raw_bytes", None)
        st.session_state.pop("bulk_import_filename", None)
        st.session_state["bulk_import_result"] = result
        st.rerun()


def _render_import_result(result) -> None:
    counts = result.counts()
    st.success("Import complete: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    for r in result.row_results:
        if r.status == "error":
            st.error(f"[{r.sheet} row {r.row}] {r.message}")
        elif r.status == "skipped":
            st.warning(f"[{r.sheet} row {r.row}] {r.message}")


def _upload_history(services) -> None:
    """Read-only view over the upload audit log (Phase 5) — kept inside
    this same Bulk Setup tab rather than Setup: it's history *about* an
    upload action taken here, not admin-editable master data like
    Skills/Teams/CCA, so it belongs next to the action it logs."""
    uploads = services.catalog_service.list_uploads()
    if not uploads:
        st.caption("No uploads yet.")
        return
    for u in uploads:
        summary = ", ".join(f"{v} {k}" for k, v in u.summary.items()) or "no summary"
        st.write(
            f"**{u.uploaded_at:%Y-%m-%d %H:%M UTC}** — {u.kind.value} `{u.filename}` "
            f"by {u.uploaded_by_name} — {summary}"
        )
        if u.errors:
            st.caption(f"{len(u.errors)} row error(s) in this upload.")


def _consolidated_scores(services, viewer: Viewer) -> None:
    agents = services.party_repo.list_by_type("agent")
    if not agents:
        st.write("No associates yet.")
        return
    labels = disambiguate_labels(agents)
    choice = st.selectbox("Associate", list(labels.keys()))
    agent = labels[choice]
    score = services.scope.consolidated_score(viewer, agent.id)
    if score is None:
        st.write("No closed assignments yet for this agent.")
    else:
        st.metric("Consolidated score", f"{score:.2f}")
