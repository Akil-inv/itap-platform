"""Setup / Configuration — admin-only, per
docs/associate_journey_redesign.md's "Setup / Configuration" section:
Skills, Teams, and CCA catalogs as master data, seeded from Excel and
addable via the UI. Deliberately its own top-level nav item, not mixed
into the daily operational screens — the kind of thing an admin walks
through once when standing up the platform and revisits occasionally.

Note: `bulk_import.py` does not seed these catalogs from Excel yet (see
docs/architecture.md's "Not built in this pass" note under the Catalog
capability) and the domain model (capabilities/catalog) has no `source`
field on Skill/Team/CcaActivity — so every entry here is, for now,
always "added in Setup." Rather than fabricate a from-Excel/from-here
distinction the data doesn't actually carry yet, this page says so
plainly; wiring bulk_import to seed these catalogs is called out as
follow-up work.
"""
from __future__ import annotations

import streamlit as st
from catalog.domain import CcaStatus

from party_helpers import disambiguate_labels


def render(services) -> None:
    st.title("Setup")
    st.caption(
        "Shared master data for Skills, Teams, and CCA activities — "
        "configured once, revisited occasionally. All entries listed "
        "below were added here; Excel-based seeding of these catalogs "
        "is not wired up yet."
    )

    col_skills, col_teams, col_cca = st.columns(3)
    with col_skills:
        _skills_column(services)
    with col_teams:
        _teams_column(services)
    with col_cca:
        _cca_column(services)


def _skills_column(services) -> None:
    st.subheader("Skills")
    skills = services.catalog_service.list_skills()
    with st.container(border=True):
        if skills:
            for s in skills:
                st.write(f"- {s.name}")
        else:
            st.caption("No skills yet.")
    with st.form("add_skill_setup"):
        name = st.text_input("New skill name")
        if st.form_submit_button("Add skill") and name:
            services.catalog_service.add_skill(name)
            st.rerun()


def _teams_column(services) -> None:
    st.subheader("Teams")
    st.caption("MVP: one Team = one Manager.")
    teams = services.catalog_service.list_teams()
    managers = services.party_repo.list_by_type("manager")
    manager_names = {m.id: m.display_name for m in managers}
    with st.container(border=True):
        if teams:
            for t in teams:
                mgr = manager_names.get(t.manager_id, "unknown manager")
                st.write(f"- **{t.name}** ({mgr})")
        else:
            st.caption("No teams yet.")
    if not managers:
        st.info("Onboard at least one Manager before adding a Team.")
        return
    manager_labels = disambiguate_labels(managers)
    with st.form("add_team_setup"):
        name = st.text_input("New team name")
        manager_choice = st.selectbox("Manager", list(manager_labels.keys()))
        if st.form_submit_button("Add team") and name:
            services.catalog_service.add_team(name, manager_labels[manager_choice].id)
            st.rerun()


def _cca_column(services) -> None:
    st.subheader("CCA activities")
    st.caption("Extra-curricular activities associates can flag interest in.")
    ccas = services.catalog_service.list_cca_activities()
    managers = services.party_repo.list_by_type("manager")
    manager_names = {m.id: m.display_name for m in managers}
    with st.container(border=True):
        if ccas:
            for c in ccas:
                organizer = manager_names.get(c.organizer_manager_id, "unknown organizer")
                st.write(f"- **{c.name}** ({organizer}) — {c.status.value}")
                if c.status == CcaStatus.OPEN:
                    if st.button("Close", key=f"close_cca_{c.id}"):
                        services.catalog_service.set_cca_status(c.id, CcaStatus.CLOSED)
                        st.rerun()
                else:
                    if st.button("Reopen", key=f"open_cca_{c.id}"):
                        services.catalog_service.set_cca_status(c.id, CcaStatus.OPEN)
                        st.rerun()
        else:
            st.caption("No CCA activities yet.")
    if not managers:
        st.info("Onboard at least one Manager before adding a CCA activity.")
        return
    manager_labels = disambiguate_labels(managers)
    with st.form("add_cca_setup"):
        name = st.text_input("New CCA activity name")
        organizer_choice = st.selectbox("Organizer (Manager)", list(manager_labels.keys()))
        if st.form_submit_button("Add CCA activity") and name:
            services.catalog_service.add_cca_activity(name, manager_labels[organizer_choice].id)
            st.rerun()
