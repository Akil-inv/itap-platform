"""Visual theme for ITAP: hides Streamlit's default chrome and applies a
card-based, app-shell look closer to a modern SPA. Pure presentation —
nothing here touches domain logic or state.

This is the ONE place that emits global CSS. It is entirely
token-driven: every color/spacing/radius/shadow value comes from
`tokens.py`, first as CSS custom properties on `:root`
(`--itap-color-...`, `--itap-space-...`, etc.) and then as the rules
below that consume those properties — so a fragment of HTML built
elsewhere (e.g. `battery.py`) can style itself with
`var(--itap-color-success)` instead of a hardcoded hex, and a future
screen can do the same instead of inventing a new value.

`home.py` used to carry its own separate inline `<style>` block
(`.itap-pitch`, `.itap-role-row`, `.itap-login-wordmark`, ...) — that
duplication is folded in here (same visual identity/copy, one origin)
so there is exactly one CSS injection point for the whole app.

Single light theme by product decision (see `.streamlit/config.toml`
and its commit message) — no dark-mode variant, no toggle.
"""
from __future__ import annotations

import streamlit as st
from tokens import TOKENS

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Libre+Franklin:wght@600;700;800"
    "&family=Source+Sans+3:wght@400;500;600;700"
    '&display=swap">'
)


def _root_vars() -> str:
    """Every design token, emitted as a CSS custom property."""
    t = TOKENS
    lines = [":root {"]
    for scale, prefix in ((t.neutral, "neutral"), (t.space, "space")):
        for key, value in scale.items():
            lines.append(f"  --itap-{prefix}-{key}: {value};")
    for key, value in t.font_size.items():
        lines.append(f"  --itap-font-size-{key}: {value};")
    for key, value in t.font_weight.items():
        lines.append(f"  --itap-font-weight-{key}: {value};")
    for key, value in t.line_height.items():
        lines.append(f"  --itap-line-height-{key}: {value};")
    lines.append(f"  --itap-font-heading: {t.font_family['heading']};")
    lines.append(f"  --itap-font-body: {t.font_family['body']};")
    for key, value in t.radius.items():
        lines.append(f"  --itap-radius-{key}: {value};")
    for key, value in t.shadow.items():
        lines.append(f"  --itap-shadow-{key}: {value};")
    for key, value in t.transition.items():
        lines.append(f"  --itap-transition-{key}: {value};")
    lines.append(f"  --itap-color-primary: {t.primary['default']};")
    lines.append(f"  --itap-color-primary-hover: {t.primary['hover']};")
    lines.append(f"  --itap-color-primary-active: {t.primary['active']};")
    lines.append(f"  --itap-color-primary-subtle: {t.primary['subtle']};")
    for key, value in t.semantic.items():
        lines.append(f"  --itap-color-{key.replace('_', '-')}: {value};")
    for key, value in t.role.items():
        lines.append(f"  --itap-color-role-{key.replace('_', '-')}: {value};")
    lines.append(f"  --itap-color-battery-current: {t.battery['current']};")
    lines.append(f"  --itap-color-battery-gap: {t.battery['gap']};")
    lines.append(f"  --itap-color-battery-gap-border: {t.battery['gap_border']};")
    for i, color in enumerate(t.battery["past_palette"]):
        lines.append(f"  --itap-color-battery-past-{i}: {color};")
    lines.append("}")
    return "\n".join(lines)


_CSS = """
<style>
__ROOT_VARS__

#MainMenu, footer, header[data-testid="stHeader"] {visibility: hidden; height: 0;}
[data-testid="stHeaderActionElements"] {display: none;}

html, body, [class*="css"] {
    font-family: var(--itap-font-body);
    font-size: var(--itap-font-size-sm);
}

h1, h2, h3, h4 {
    font-family: var(--itap-font-heading);
}

.block-container {
    padding-top: var(--itap-space-2xl);
    max-width: 1100px;
}

h1 {
    font-weight: var(--itap-font-weight-heavy);
    letter-spacing: -0.02em;
    margin-bottom: var(--itap-space-2xs);
}

section[data-testid="stSidebar"] {
    background-color: var(--itap-neutral-50);
    border-right: 1px solid var(--itap-neutral-150);
}

div[data-testid="stForm"] {
    border: 1px solid var(--itap-neutral-150);
    border-radius: var(--itap-radius-lg);
    padding: var(--itap-space-xl) var(--itap-space-xl) var(--itap-space-sm) var(--itap-space-xl);
    background: var(--itap-neutral-0);
    box-shadow: var(--itap-shadow-resting);
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: var(--itap-radius-lg) !important;
    box-shadow: var(--itap-shadow-resting);
    transition: box-shadow var(--itap-transition-base);
}

/* Interaction states: buttons ------------------------------------------ */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
    border-radius: var(--itap-radius-md);
    font-weight: var(--itap-font-weight-semibold);
    padding: 0.4rem 1.1rem;
    transition: background-color var(--itap-transition-fast),
        border-color var(--itap-transition-fast),
        box-shadow var(--itap-transition-fast),
        transform var(--itap-transition-fast);
}
.stButton > button:hover:not(:disabled),
.stFormSubmitButton > button:hover:not(:disabled),
.stDownloadButton > button:hover:not(:disabled) {
    border-color: var(--itap-color-primary);
    color: var(--itap-color-primary);
    transform: translateY(-1px);
}
.stButton > button:active:not(:disabled),
.stFormSubmitButton > button:active:not(:disabled) {
    transform: translateY(0);
}
.stButton > button:focus-visible,
.stFormSubmitButton > button:focus-visible,
.stDownloadButton > button:focus-visible,
a:focus-visible,
[tabindex]:focus-visible {
    outline: 2px solid var(--itap-color-primary);
    outline-offset: 2px;
}
.stButton > button:disabled,
.stFormSubmitButton > button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
    box-shadow: none;
}

.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background-color: var(--itap-color-primary);
    border-color: var(--itap-color-primary);
}
.stButton > button[kind="primary"]:hover:not(:disabled),
.stFormSubmitButton > button[kind="primary"]:hover:not(:disabled) {
    background-color: var(--itap-color-primary-hover);
    border-color: var(--itap-color-primary-hover);
    color: var(--itap-neutral-0);
}

div[data-testid="stMetric"] {
    background: var(--itap-neutral-50);
    border: 1px solid var(--itap-neutral-150);
    border-radius: var(--itap-radius-lg);
    padding: var(--itap-space-md) var(--itap-space-lg);
}

/* Journey stepper -------------------------------------------------------- */
.itap-stepper {
    display: flex;
    align-items: center;
    margin: var(--itap-space-sm) 0 var(--itap-space-xl) 0;
}
.itap-step {
    display: flex;
    align-items: center;
    flex: 1;
}
.itap-step-circle {
    width: 28px;
    height: 28px;
    border-radius: var(--itap-radius-circle);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--itap-font-size-xs);
    font-weight: var(--itap-font-weight-bold);
    flex-shrink: 0;
}
.itap-step-label {
    margin-left: var(--itap-space-sm);
    font-size: var(--itap-font-size-xs);
    font-weight: var(--itap-font-weight-semibold);
    white-space: nowrap;
}
.itap-step-line {
    flex: 1;
    height: 2px;
    margin: 0 var(--itap-space-md);
}
.itap-step-done .itap-step-circle { background-color: var(--itap-color-success); color: var(--itap-neutral-0); }
.itap-step-done .itap-step-label { color: var(--itap-color-success); }
.itap-step-current .itap-step-circle { background-color: var(--itap-color-primary); color: var(--itap-neutral-0); }
.itap-step-current .itap-step-label { color: var(--itap-color-primary); }
.itap-step-upcoming .itap-step-circle { background-color: var(--itap-neutral-150); color: var(--itap-neutral-500); }
.itap-step-upcoming .itap-step-label { color: var(--itap-neutral-500); }
.itap-step-line-done { background-color: var(--itap-color-success); }
.itap-step-line-upcoming { background-color: var(--itap-neutral-150); }

/* Tenure battery meter ---------------------------------------------------
   A real meter: a track (subtle recessed capsule) that the segments sit
   inside, rather than loose colored slivers floating next to a name. */
.itap-battery-wrap {
    display: inline-flex;
    align-items: center;
    gap: var(--itap-space-xs);
}
.itap-battery {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    flex-wrap: wrap;
    background: var(--itap-neutral-150);
    border: 1px solid var(--itap-neutral-300);
    border-radius: var(--itap-radius-pill);
    padding: 3px;
    box-shadow: var(--itap-shadow-recessed);
}
.itap-battery-seg {
    width: 18px;
    height: 14px;
    border-radius: 3px;
    box-shadow: inset 0 0 0 1px rgba(27,34,51,0.06);
}
.itap-battery-seg--gap {
    background-image: repeating-linear-gradient(
        45deg, var(--itap-color-battery-gap-border), var(--itap-color-battery-gap-border) 2px,
        transparent 2px, transparent 5px
    );
}
.itap-battery-caption {
    font-size: var(--itap-font-size-xs);
    color: var(--itap-neutral-500);
    white-space: nowrap;
}

/* Avatar -------------------------------------------------------------- */
.itap-avatar {
    width: 44px;
    height: 44px;
    border-radius: var(--itap-radius-circle);
    background: var(--itap-color-primary-subtle);
    color: var(--itap-color-role-functional-owner);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--itap-font-size-lg);
    font-weight: var(--itap-font-weight-bold);
    flex-shrink: 0;
    overflow: hidden;
}
.itap-avatar img { width: 100%; height: 100%; object-fit: cover; }
.itap-avatar--lg { width: 72px; height: 72px; font-size: var(--itap-font-size-xxl); }

/* Person list row --------------------------------------------------------
   One reusable "clickable person row" component: avatar + name + meter +
   status, composed as one card. The name is still a real st.button (a
   Streamlit constraint) but is restyled from a big centered pill into a
   left-aligned row control that fills the row. */
.itap-person-row {
    display: flex;
    align-items: center;
    gap: var(--itap-space-lg);
}
.itap-person-row .itap-person-meta {
    display: flex;
    flex-direction: column;
    gap: var(--itap-space-3xs);
    min-width: 0;
}
.itap-person-row .itap-person-sub {
    font-size: var(--itap-font-size-xs);
    color: var(--itap-neutral-500);
}
div[class*="st-key-person_row_"] {
    box-shadow: var(--itap-shadow-resting);
    transition: box-shadow var(--itap-transition-base);
}
div[class*="st-key-person_row_"]:hover {
    box-shadow: var(--itap-shadow-hover);
}
div[class*="st-key-person_row_"] .stButton > button {
    background: transparent;
    border: none;
    box-shadow: none;
    padding: var(--itap-space-3xs) 0;
    font-size: var(--itap-font-size-base);
    font-weight: var(--itap-font-weight-semibold);
    color: var(--itap-neutral-900);
    text-align: left;
    justify-content: flex-start;
    width: 100%;
    border-radius: var(--itap-radius-sm);
}
/* Streamlit wraps the button label in its own inner flex container that
   centers itself regardless of the button's own justify-content — that
   inner wrapper has to be told to left-align too, or the outer rule above
   has no visible effect. */
div[class*="st-key-person_row_"] .stButton > button > div {
    justify-content: flex-start;
    width: 100%;
}
div[class*="st-key-person_row_"] .stButton > button:hover:not(:disabled) {
    color: var(--itap-color-primary);
    text-decoration: underline;
    transform: none;
}

/* Badges / chips --------------------------------------------------------- */
.itap-interest-badge {
    display: inline-block;
    font-size: var(--itap-font-size-xs);
    font-weight: var(--itap-font-weight-bold);
    color: var(--itap-neutral-0);
    background-color: var(--itap-color-role-manager);
    border-radius: var(--itap-radius-pill);
    padding: 0.1rem 0.55rem;
    margin-left: var(--itap-space-xs);
    vertical-align: middle;
}
.itap-status-chip {
    display: inline-block;
    font-size: var(--itap-font-size-xs);
    font-weight: var(--itap-font-weight-bold);
    border-radius: var(--itap-radius-pill);
    padding: 0.15rem 0.6rem;
}
.itap-status-active { background-color: var(--itap-color-success-subtle); color: var(--itap-color-success); }
.itap-status-attention { background-color: var(--itap-color-error-subtle); color: var(--itap-color-error); }
.itap-status-available { background-color: var(--itap-color-info-subtle); color: var(--itap-color-info); }
.itap-status-completed { background-color: var(--itap-neutral-150); color: var(--itap-neutral-600); }

/* Rotation timeline (portfolio page) -------------------------------------- */
.itap-stage-card {
    border-left: 4px solid var(--itap-neutral-150);
    padding: var(--itap-space-2xs) 0 var(--itap-space-2xs) var(--itap-space-lg);
    margin-bottom: var(--itap-space-2xs);
}
.itap-stage-card.itap-stage-active { border-left-color: var(--itap-color-role-agent); }
.itap-stage-card.itap-stage-gap { border-left-color: var(--itap-neutral-300); border-left-style: dashed; }

/* Sign-in / home page (folded in from the former home.py-local CSS) ------ */
.itap-pitch-eyebrow {
    font-size: 12.5px; font-weight: var(--itap-font-weight-bold); letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--itap-color-role-functional-owner);
}
.itap-pitch h1 {
    font-family: var(--itap-font-heading);
    font-size: 2.4rem; font-weight: var(--itap-font-weight-heavy); letter-spacing: -0.01em;
    text-wrap: balance; margin: 10px 0 0 0; color: var(--itap-neutral-900);
}
.itap-pitch p.lede { color: var(--itap-neutral-600); font-size: 1.02rem; max-width: 46ch; margin-top: 14px; }
.itap-role-row {
    display: flex; align-items: flex-start; gap: var(--itap-space-md);
    padding: var(--itap-space-md) var(--itap-space-lg); background: var(--itap-neutral-0);
    border: 1px solid var(--itap-neutral-200);
    border-radius: var(--itap-radius-md); margin-top: var(--itap-space-sm);
    box-shadow: var(--itap-shadow-resting);
    transition: box-shadow var(--itap-transition-base);
}
.itap-role-row:hover { box-shadow: var(--itap-shadow-hover); }
.itap-role-dot { width: 10px; height: 10px; border-radius: var(--itap-radius-circle); flex-shrink: 0; margin-top: 5px; }
.itap-role-row .rname { font-weight: var(--itap-font-weight-semibold); font-size: 13.5px; }
.itap-role-row .rdesc { color: var(--itap-neutral-600); font-size: var(--itap-font-size-xs); }
.itap-login-wordmark {
    font-family: var(--itap-font-heading);
    font-size: 1.5rem; font-weight: var(--itap-font-weight-heavy); letter-spacing: -0.02em;
}
.itap-login-wordmark span { color: var(--itap-color-role-functional-owner); }
.itap-login-sub { color: var(--itap-neutral-600); font-size: 13.5px; margin-top: 4px; margin-bottom: 4px; }
.itap-role-heading { font-weight: var(--itap-font-weight-bold); font-size: 13.5px; margin-top: 4px; }
.itap-role-heading .dot { display:inline-block; width:9px; height:9px; border-radius:var(--itap-radius-circle); margin-right:6px; }

@media (prefers-reduced-motion: reduce) {
    * { transition-duration: 0.001ms !important; }
}
</style>
"""


def inject() -> None:
    st.markdown(_FONTS, unsafe_allow_html=True)
    st.markdown(_CSS.replace("__ROOT_VARS__", _root_vars()), unsafe_allow_html=True)
