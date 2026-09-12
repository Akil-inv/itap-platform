"""Visual theme for ITAP: hides Streamlit's default chrome and applies a
card-based, app-shell look closer to a modern SPA. Pure presentation —
nothing here touches domain logic or state.
"""
from __future__ import annotations

import streamlit as st

_CSS = """
<style>
#MainMenu, footer, header[data-testid="stHeader"] {visibility: hidden; height: 0;}

html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI",
        Roboto, Helvetica, Arial, sans-serif;
}

.block-container {
    padding-top: 2rem;
    max-width: 1100px;
}

h1 {
    font-weight: 700;
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
    st.markdown(_CSS, unsafe_allow_html=True)
