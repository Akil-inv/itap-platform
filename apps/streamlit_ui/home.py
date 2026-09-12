"""The product's landing/sign-in screen — one page, styled per the
approved front-page mockup: a pitch panel ("one address, three
experiences") next to the actual sign-in card. This is still the one
place identity selection happens (not a sidebar dropdown), and still the
same dev-mode stand-in underneath (no real auth yet — see
docs/architecture.md): picking your name from the grouped list below is
what "signing in" means today. Real auth only replaces that one picker;
everything downstream (services, views, RBAC) already only needs a
Viewer, however it gets constructed.
"""
from __future__ import annotations

import streamlit as st
from party_identity.domain import Party
from rbac_scope import Role

from party_helpers import disambiguate_labels
from role_labels import ROLE_DISPLAY_NAME

# Descriptions/colors for the three roles on the sign-in page. Names come
# from role_labels.ROLE_DISPLAY_NAME so the header (app.py) calls each role
# the same thing.
ROLE_SECTIONS = [
    (
        Role.FUNCTIONAL_OWNER,
        ROLE_DISPLAY_NAME[Role.FUNCTIONAL_OWNER],
        "Runs the whole program: onboarding, assignments, org-wide oversight.",
        "#333F6B",
    ),
    (
        Role.MANAGER,
        ROLE_DISPLAY_NAME[Role.MANAGER],
        "Sets goals, tracks and closes out the associates on their team.",
        "#16707F",
    ),
    (
        Role.AGENT,
        ROLE_DISPLAY_NAME[Role.AGENT],
        "Tracks their own goals, journey, and gives feedback.",
        "#3F7D57",
    ),
]

_CSS = """
<style>
.itap-pitch-eyebrow {
    font-size: 12.5px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: #333F6B;
}
.itap-pitch h1 {
    font-family: "Libre Franklin", "Source Sans 3", sans-serif;
    font-size: 2.4rem; font-weight: 800; letter-spacing: -0.01em;
    text-wrap: balance; margin: 10px 0 0 0; color: #1B2233;
}
.itap-pitch p.lede { color: #5B6475; font-size: 1.02rem; max-width: 46ch; margin-top: 14px; }
.itap-role-row {
    display: flex; align-items: flex-start; gap: 12px;
    padding: 12px 14px; background: #FFFFFF; border: 1px solid #DEE2E9;
    border-radius: 10px; margin-top: 10px;
    box-shadow: 0 1px 2px rgba(27,34,51,0.04), 0 6px 20px rgba(27,34,51,0.06);
}
.itap-role-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }
.itap-role-row .rname { font-weight: 600; font-size: 13.5px; }
.itap-role-row .rdesc { color: #5B6475; font-size: 13px; }
.itap-login-wordmark {
    font-family: "Libre Franklin", "Source Sans 3", sans-serif;
    font-size: 1.5rem; font-weight: 800; letter-spacing: -0.02em;
}
.itap-login-wordmark span { color: #333F6B; }
.itap-login-sub { color: #5B6475; font-size: 13.5px; margin-top: 4px; margin-bottom: 4px; }
.itap-role-heading { font-weight: 700; font-size: 13.5px; margin-top: 4px; }
.itap-role-heading .dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px; }
</style>
"""


def render(services) -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.write("")
    st.write("")

    pitch_col, card_col = st.columns([1.1, 1], gap="large")

    with pitch_col:
        st.markdown(
            '<div class="itap-pitch">'
            '<div class="itap-pitch-eyebrow">One address, three experiences</div>'
            "<h1>Sign in once. ITAP shows you your own program.</h1>"
            '<p class="lede">There\'s a single sign-in — no separate admin, '
            "manager, or associate sites to remember. What you see once "
            "you're in is decided entirely by your role.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.write("")
        for role, heading, subtitle, color in ROLE_SECTIONS:
            st.markdown(
                f'<div class="itap-role-row">'
                f'<span class="itap-role-dot" style="background:{color};"></span>'
                f'<div><div class="rname">{heading}</div>'
                f'<div class="rdesc">{subtitle}</div></div>'
                f"</div>",
                unsafe_allow_html=True,
            )

    with card_col:
        with st.container(border=True):
            st.markdown(
                '<div class="itap-login-wordmark">IT<span>AP</span></div>'
                '<div class="itap-login-sub">Intern Training &amp; Assignment Platform</div>',
                unsafe_allow_html=True,
            )
            st.divider()

            any_people = False
            for role, heading, subtitle, color in ROLE_SECTIONS:
                parties = services.party_repo.list_by_type(role.value)
                if not parties:
                    continue
                any_people = True
                st.markdown(
                    f'<div class="itap-role-heading">'
                    f'<span class="dot" style="background:{color};"></span>{heading}'
                    f"</div>",
                    unsafe_allow_html=True,
                )
                labels = disambiguate_labels(parties, label_fn=lambda p: p.display_name)
                cols = st.columns(min(len(labels), 3) or 1)
                for i, (label, party) in enumerate(labels.items()):
                    with cols[i % len(cols)]:
                        if st.button(label, key=f"signin_{party.id}", width="stretch"):
                            st.session_state["viewer_party_id"] = str(party.id)
                            st.rerun()
                st.write("")

            if not any_people:
                st.info("No one is set up yet — add the first ITAP Admin below.")

            st.divider()
            with st.expander("Add a new person (ITAP Admin setup)"):
                st.caption(
                    "Email is optional today, but is the field a future SSO "
                    "integration would match against — worth filling in now. "
                    "On a brand-new deployment, use this to create the first "
                    "ITAP Admin, then sign in as them and use Bulk Setup for "
                    "everyone else."
                )
                col0, col1, col2 = st.columns(3)
                with col0:
                    with st.form("home_new_admin"):
                        name = st.text_input("Admin name", key="home_admin_name")
                        email = st.text_input("Email (optional)", key="home_admin_email")
                        if st.form_submit_button("Create ITAP Admin") and name:
                            attrs = {"email": email} if email else {}
                            services.party_repo.add(
                                Party(
                                    party_type="functional_owner",
                                    display_name=name,
                                    attributes=attrs,
                                )
                            )
                            st.rerun()
                with col1:
                    with st.form("home_new_agent"):
                        name = st.text_input("Associate name")
                        email = st.text_input("Email (optional)", key="home_agent_email")
                        if st.form_submit_button("Create Associate") and name:
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
