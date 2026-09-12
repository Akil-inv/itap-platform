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
from tokens import TOKENS

# Descriptions/colors for the three roles on the sign-in page. Names come
# from role_labels.ROLE_DISPLAY_NAME so the header (app.py) calls each role
# the same thing. Colors come from tokens.ROLE — the one place the three
# role identity colors are defined.
ROLE_SECTIONS = [
    (
        Role.FUNCTIONAL_OWNER,
        ROLE_DISPLAY_NAME[Role.FUNCTIONAL_OWNER],
        "Runs the whole program: onboarding, assignments, org-wide oversight.",
        TOKENS.role["functional_owner"],
    ),
    (
        Role.MANAGER,
        ROLE_DISPLAY_NAME[Role.MANAGER],
        "Sets goals, tracks and closes out the associates on their team.",
        TOKENS.role["manager"],
    ),
    (
        Role.AGENT,
        ROLE_DISPLAY_NAME[Role.AGENT],
        "Tracks their own goals, journey, and gives feedback.",
        TOKENS.role["agent"],
    ),
]

def render(services) -> None:
    # Styling for .itap-pitch / .itap-role-row / .itap-login-wordmark etc.
    # now lives in theme.py's single global stylesheet (folded in from
    # this module's former local _CSS block) — theme.inject() is called
    # once in app.py before any view renders, so nothing needs injecting
    # here.
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

            # Solves exactly one problem: a genuinely empty deployment has no
            # one to click on this sign-in page, so there is no way in at
            # all. This is deliberately Admin-only and deliberately only
            # shown while no one exists yet — it is not a general "add
            # anyone" convenience. Every other role comes from Bulk Setup
            # (or the authenticated, admin-only Onboard & Assign back door),
            # per docs/associate_journey_redesign.md's "no loose profiles"
            # principle; a public, unauthenticated sign-in page has no
            # business creating Managers or Associates.
            if not any_people:
                st.info("No one is set up yet — add the first ITAP Admin below.")
                with st.expander("Add the first ITAP Admin", expanded=True):
                    st.caption(
                        "Email is optional today, but is the field a future SSO "
                        "integration would match against — worth filling in now. "
                        "Once created, sign in as them and use Bulk Setup to "
                        "bring in everyone else."
                    )
                    with st.form("home_new_admin"):
                        name = st.text_input("Admin name", key="home_new_admin_name")
                        email = st.text_input("Email (optional)", key="home_new_admin_email")
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
