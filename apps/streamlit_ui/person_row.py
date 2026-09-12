"""One reusable "clickable person row" component — avatar + name + tenure
meter + status, composed inside a single visual card — replacing the
pattern that used to be duplicated (and inconsistent) across the admin's
Associates list and the Manager's My Team list: a raw, full-width
`st.button` sitting alone in its own bordered box, next to a
disconnected, unstyled battery bar.

Streamlit still requires a real widget for the click target (there's no
way to make a plain HTML element post an event back to the server), so
the name is still an `st.button` — but it's restyled here (via
`theme.py`'s `div[class*="st-key-person_row_"] .stButton > button` rule)
to read as a left-aligned row control that fills the row, not a big
centered pill floating next to the rest of the row's content.

Usage:

    clicked, extra_cols = render_person_row(
        key=str(agent.id),
        display_name=agent.display_name,
        photo_url=profile.photo_url if profile else None,
        sub_label="Current team: Data Team",
        battery_html=render_battery_html(all_assignments),
        extra_col_weights=[2, 1],
    )
    with extra_cols[0]:
        ...  # status chip, score, etc.
    if clicked:
        ...  # open the level-2 page

`extra_col_weights` lets each caller add its own trailing columns (status
chip, current-team label, score reveal, ...) without forking the shared
avatar/name/meter layout.
"""
from __future__ import annotations

import html
from typing import Optional

import streamlit as st


def avatar_html(display_name: str, photo_url: Optional[str] = None, large: bool = False) -> str:
    """The avatar/initials circle used both in this row component and in
    the level-2 profile page headers (`views/associate_portfolio.py`,
    `views/manager_associate.py`, `views/agent.py`) — one implementation
    instead of three copies of the same inline `<div style=...>`."""
    css_class = "itap-avatar itap-avatar--lg" if large else "itap-avatar"
    if photo_url:
        return f'<div class="{css_class}"><img src="{html.escape(photo_url)}" alt=""></div>'
    initial = html.escape(display_name[:1].upper()) if display_name else "?"
    return f'<div class="{css_class}">{initial}</div>'


def render_person_row(
    *,
    key: str,
    display_name: str,
    photo_url: Optional[str] = None,
    sub_label: Optional[str] = None,
    battery_html: Optional[str] = None,
    extra_col_weights: Optional[list[float]] = None,
) -> tuple[bool, list]:
    """Renders one person row inside a bordered card. Returns
    `(clicked, extra_cols)`: `clicked` is True the run the name button was
    pressed; `extra_cols` are the trailing `st.columns` the caller asked
    for via `extra_col_weights`, left open for status chips/labels/score
    reveals so every screen using this row still composes its own extra
    content without duplicating the avatar/name/meter part."""
    extra_col_weights = extra_col_weights or []
    weights = [0.6, 3.0, 2.2] + list(extra_col_weights)

    with st.container(border=True, key=f"person_row_{key}"):
        cols = st.columns(weights, vertical_alignment="center")
        with cols[0]:
            st.markdown(avatar_html(display_name, photo_url), unsafe_allow_html=True)
        with cols[1]:
            clicked = st.button(display_name, key=f"open_{key}", width="stretch")
            if sub_label:
                st.markdown(
                    f'<div class="itap-person-sub">{html.escape(sub_label)}</div>',
                    unsafe_allow_html=True,
                )
        with cols[2]:
            if battery_html:
                st.markdown(
                    '<div class="itap-battery-caption">Tenure</div>' + battery_html,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="itap-battery-caption">No history yet</div>',
                    unsafe_allow_html=True,
                )
        return clicked, list(cols[3:])
