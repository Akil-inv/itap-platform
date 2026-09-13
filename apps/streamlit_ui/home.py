"""The product's landing/sign-in screen — one page, styled per the
approved front-page mockup: a pitch panel ("one address, three
experiences") next to the actual sign-in card. This is still the one
place identity selection happens (not a sidebar dropdown).

Three ways this card can render, checked in this order — see
`render()`:

1. **No one onboarded yet** — the one-time "Add the first ITAP Admin"
   bootstrap form, regardless of anything below. Nobody to authenticate
   against yet, AD or otherwise.
2. **AD login configured** (`ad_auth.is_configured()`) — a real
   username + password form, authenticated by an LDAP bind against your
   corporate Active Directory (`ad_auth.py`). This is the one that
   belongs in an actual deployment.
3. **Neither** — the dev-mode picker: click any name from the grouped
   list below, no credentials at all. A stand-in for real auth, not a
   security boundary — see `ad_auth.py`/`sso_auth.py` and
   docs/architecture.md.

Real auth only ever replaces this one card; everything downstream
(services, views, RBAC) already only needs a Viewer, however it gets
constructed. CML SSO passthrough (`sso_auth.py`, checked in `app.py`
before this module is ever reached) is the other real-auth path — AD
login here is for when that isn't available yet, or the app runs
somewhere outside CML's own proxy entirely.
"""
from __future__ import annotations

import ad_auth
import sso_auth
import streamlit as st
from party_helpers import disambiguate_labels
from party_identity.domain import Party
from rbac_scope import Role
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

    with card_col, st.container(border=True):
        st.markdown(
            '<div class="itap-login-wordmark">IT<span>AP</span></div>'
            '<div class="itap-login-sub">Intern Training &amp; Assignment Platform</div>',
            unsafe_allow_html=True,
        )
        st.divider()

        any_people = any(
            services.party_repo.list_by_type(role.value) for role, *_ in ROLE_SECTIONS
        )

        if any_people and ad_auth.is_configured():
            _ad_login_form(services)
        elif any_people:
            _picker(services)

        # Solves exactly one problem: a genuinely empty deployment has no
        # one to click on this sign-in page, so there is no way in at
        # all. This is deliberately Admin-only and deliberately only
        # shown while no one exists yet — it is not a general "add
        # anyone" convenience. Every other role comes from Bulk Setup
        # (or the authenticated, admin-only Onboard & Assign back door),
        # per docs/associate_journey_redesign.md's "no loose profiles"
        # principle; a public, unauthenticated sign-in page has no
        # business creating Managers or Associates. Shown regardless of
        # AD config — nobody to authenticate against yet either way.
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


def _picker(services) -> None:
    """The dev-mode "click any name" picker — no credentials at all.
    Shown only when AD login isn't configured (`ad_auth.is_configured()`
    is False); see this module's docstring for the full precedence."""
    for role, heading, subtitle, color in ROLE_SECTIONS:
        parties = services.party_repo.list_by_type(role.value)
        if not parties:
            continue
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


def _ad_login_form(services) -> None:
    """A real username + password login, authenticated by an LDAP bind
    against Active Directory (`ad_auth.py`) — shown instead of the
    dev-mode picker once `AD_SERVER` is configured. A wrong password (or
    an unreachable AD server) and an account that binds fine but has no
    matching ITAP Party both show the same generic error — a login form
    should never reveal which case it was."""
    st.caption("Sign in with your organization account.")
    with st.form("ad_login"):
        username = st.text_input("Username", key="ad_login_username")
        password = st.text_input("Password", type="password", key="ad_login_password")
        submitted = st.form_submit_button("Sign in", type="primary", width="stretch")

    if not submitted:
        return

    ad_user = ad_auth.authenticate(username, password)
    if ad_user is None:
        st.error("Invalid username or password.")
        return

    identity = ad_user.email or ad_user.username
    party = sso_auth.find_party_by_sso_identity(services.party_repo, identity)
    if party is None:
        st.error(
            "That's a valid organization login, but no ITAP account is "
            "provisioned for it yet. Ask your ITAP Admin to onboard you "
            "(matching this email), then try again."
        )
        return

    st.session_state["viewer_party_id"] = str(party.id)
    # app.py forces the dev-mode "Switch person" control off for the rest
    # of this session when this is set — same reasoning as its SSO-header
    # case: someone who just authenticated with a real AD password must
    # never be able to fall back to the picker and impersonate someone
    # else, misconfiguration or not.
    st.session_state["authenticated_via"] = "ad"
    st.rerun()
