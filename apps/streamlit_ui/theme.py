"""Visual theme for ITAP: hides Streamlit's default chrome and applies a
card-based, app-shell look closer to a modern SPA. Pure presentation —
nothing here touches domain logic or state.
"""
from __future__ import annotations

import streamlit as st

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Libre+Franklin:wght@600;700;800"
    "&family=Source+Sans+3:wght@400;500;600;700"
    '&display=swap">'
)

# Same type system as the approved front-page mockup: Libre Franklin for
# headings, Source Sans 3 for body text — not the generic system-font
# stack the app shipped with before that mockup existed.
_CSS = """
<style>
#MainMenu, footer, header[data-testid="stHeader"] {visibility: hidden; height: 0;}
[data-testid="stHeaderActionElements"] {display: none;}

html, body, [class*="css"] {
    font-family: "Source Sans 3", -apple-system, BlinkMacSystemFont,
        "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

h1, h2, h3, h4 {
    font-family: "Libre Franklin", "Source Sans 3", sans-serif;
}

.block-container {
    padding-top: 2rem;
    max-width: 1100px;
}

h1 {
    font-weight: 800;
    letter-spacing: -0.02em;
    margin-bottom: 0.25rem;
}

section[data-testid="stSidebar"] {
    background-color: #F7F8FA;
    border-right: 1px solid #E4E7EB;
}

div[data-testid="stForm"] {
    border: 1px solid #E4E7EB;
    border-radius: 12px;
    padding: 1.25rem 1.25rem 0.5rem 1.25rem;
    background: #FFFFFF;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    box-shadow: 0 1px 2px rgba(27,34,51,0.04), 0 6px 20px rgba(27,34,51,0.06);
}

div[data-testid="stForm"] {
    box-shadow: 0 1px 2px rgba(27,34,51,0.04), 0 6px 20px rgba(27,34,51,0.06);
}

.stButton > button, .stFormSubmitButton > button {
    border-radius: 8px;
    font-weight: 600;
    padding: 0.4rem 1.1rem;
}

.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background-color: #4C78A8;
    border-color: #4C78A8;
}

div[data-testid="stMetric"] {
    background: #F7F8FA;
    border: 1px solid #E4E7EB;
    border-radius: 12px;
    padding: 0.75rem 1rem;
}

/* Journey stepper */
.itap-stepper {
    display: flex;
    align-items: center;
    margin: 0.5rem 0 1.25rem 0;
}
.itap-step {
    display: flex;
    align-items: center;
    flex: 1;
}
.itap-step-circle {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
    font-weight: 700;
    flex-shrink: 0;
}
.itap-step-label {
    margin-left: 0.5rem;
    font-size: 0.85rem;
    font-weight: 600;
    white-space: nowrap;
}
.itap-step-line {
    flex: 1;
    height: 2px;
    margin: 0 0.75rem;
}
.itap-step-done .itap-step-circle {
    background-color: #54A24B;
    color: white;
}
.itap-step-done .itap-step-label { color: #54A24B; }
.itap-step-current .itap-step-circle {
    background-color: #4C78A8;
    color: white;
}
.itap-step-current .itap-step-label { color: #4C78A8; }
.itap-step-upcoming .itap-step-circle {
    background-color: #E4E7EB;
    color: #8A94A6;
}
.itap-step-upcoming .itap-step-label { color: #8A94A6; }
.itap-step-line-done { background-color: #54A24B; }
.itap-step-line-upcoming { background-color: #E4E7EB; }
</style>
"""


def inject() -> None:
    st.markdown(_FONTS, unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)
