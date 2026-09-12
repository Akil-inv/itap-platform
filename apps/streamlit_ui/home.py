"""The product's landing/sign-in screen. This is the one place identity
selection happens — not a sidebar dropdown, per the product direction
that content should feel driven by "who's using the product" rather than
"which database row is selected." Under the hood this is still the same
dev-mode stand-in (no real auth yet — see docs/architecture.md), just
given an actual product front door instead of a raw picker.
"""
from __future__ import annotations

import streamlit as st
from party_identity.domain import Party
from rbac_scope import Role

from party_helpers import disambiguate_labels

ROLE_SECTIONS = [
    (Role.FUNCTIONAL_OWNER, "Functional Owner", "Runs the whole program."),
    (Role.MANAGER, "Managers", "Lead a team of Agents."),
    (Role.AGENT, "Agents", "In training, tracking their own journey."),
]


def render(services) -> None:
    st.markdown(
        '<div style="text-align:center; margin-top: 2rem; margin-bottom: 2rem;">'
        '<div style="font-size: 2.6rem; font-weight: 800; letter-spacing: -0.03em;">ITAP</div>'
        '<div style="font-size: 1.05rem; color: #6B7280; margin-top: 0.25rem;">'
        "Intern Training &amp; Assignment Platform</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p style="text-align:center; color:#6B7280;">Choose who you are to continue.</p>',
        unsafe_allow_html=True,
    )

    for role, heading, subtitle in ROLE_SECTIONS:
        parties = services.party_repo.list_by_type(role.value)
        if not parties:
            continue
        st.markdown(f"**{heading}** — {subtitle}")
        labels = disambiguate_labels(parties, label_fn=lambda p: p.display_name)
        cols = st.columns(min(len(labels), 4) or 1)
        for i, (label, party) in enumerate(labels.items()):
            with cols[i % len(cols)]:
                if st.button(label, key=f"signin_{party.id}", width='stretch'):
                    st.session_state["viewer_party_id"] = str(party.id)
                    st.rerun()
        st.write("")

    st.divider()
    with st.expander("Add a new person (Functional Owner setup)"):
        st.caption(
            "Email is optional today, but is the field a future SSO "
            "integration would match against — worth filling in now."
        )
        col1, col2 = st.columns(2)
        with col1:
            with st.form("home_new_agent"):
                name = st.text_input("Agent name")
                email = st.text_input("Email (optional)", key="home_agent_email")
                if st.form_submit_button("Create Agent") and name:
                    attrs = {"email": email} if email else {}
                    services.party_repo.add(
                        Party(party_type="agent", display_name=name, attributes=attrs)
                    )
                    st.rerun()
        with col2:
            with st.form("home_new_manager"):
                name = st.text_input("Manager name", key="home_manager_name")
                email = st.text_input("Email (optional)", key="home_manager_email")
                if st.form_submit_button("Create Manager") and name:
                    attrs = {"email": email} if email else {}
                    services.party_repo.add(
                        Party(party_type="manager", display_name=name, attributes=attrs)
                    )
                    st.rerun()
