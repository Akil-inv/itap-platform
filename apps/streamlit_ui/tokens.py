"""ITAP design tokens — the single source of truth for color, type,
spacing, radius, and elevation across the Streamlit UI.

Why this exists: before this file, `theme.py`, `home.py`, `battery.py`,
and every `views/*.py` module picked their own hex colors, paddings, and
radii independently. Nothing guaranteed two "same meaning" things (e.g.
two status chips, two card borders) actually matched, and no component
was designed once and reused — see docs/architecture.md's design-system
section for the incident that prompted this file (the Manager's My Team
list: a bare `st.button` next to an unstyled battery bar).

This app is pinned to a single light theme (see
`.streamlit/config.toml` and its commit message) — there is no dark-mode
variant of these tokens, and none should be added here.

Usage: `theme.py` turns every value below into a CSS custom property
(`--itap-color-...`) in the injected stylesheet, so HTML fragments
built by `battery.py`/views can reference `var(--itap-color-success)`
etc. instead of a hardcoded hex. Python-side consumers that render into
an isolated `st.iframe` document (`journey_curve.py`, `org_tree.py`,
which cannot see the page's CSS custom properties) import the raw
Python constants directly from here instead of duplicating hex values.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# --- Neutrals ---------------------------------------------------------
# A light-mode gray ramp built by varying lightness only, 0 (white) to
# 900 (near-black text), not by picking unrelated grays.
NEUTRAL = {
    0: "#FFFFFF",
    50: "#F7F8FA",
    100: "#F0F2F5",
    150: "#E4E7EB",
    200: "#DEE2E9",
    300: "#C7CDD6",
    400: "#AEB6C2",
    500: "#8A94A6",
    600: "#5B6475",
    700: "#3D4454",
    800: "#232A3B",
    900: "#1B2233",
}

# --- Primary / brand ---------------------------------------------------
# One brand color, reused exactly as it already appears across the app
# for primary actions and links.
PRIMARY = {
    "default": "#4C78A8",
    "hover": "#3F6690",
    "active": "#365A7E",
    "subtle": "#EAF1F8",  # tinted background for selected/active surfaces
}

# --- Semantic colors -----------------------------------------------------
# Consolidates the ad hoc success/warning/error/info colors that were
# previously scattered (e.g. #54A24B / #3F7D57 for success, #B45309-ish
# ambers for warning) into one definition per meaning, each with a
# matching light "subtle" background for chips/badges.
SEMANTIC = {
    "success": "#3F7D57",
    "success_subtle": "#E3F1E6",
    "warning": "#B9791A",
    "warning_subtle": "#FBF1E1",
    "error": "#B24A2C",
    "error_subtle": "#FBEAE3",
    "info": "#333F6B",
    "info_subtle": "#EAF1F8",
}

# --- Role identity colors -----------------------------------------------
# Brand identity colors for the three roles — kept exactly as-is per
# product decision, just centralized so every screen references the same
# three values instead of re-typing them.
ROLE = {
    "functional_owner": "#333F6B",  # admin navy
    "manager": "#16707F",           # manager teal
    "agent": "#3F7D57",             # associate green
}

# --- Tenure battery palette -----------------------------------------------
# Distinct colors for successive past Primary stints, plus the current
# stint and gap colors. Kept separate from SEMANTIC/ROLE because these
# are identity colors for a specific person's Nth past stint, not a
# status meaning.
BATTERY = {
    "current": SEMANTIC["success"],
    "gap": NEUTRAL[200],
    "gap_border": NEUTRAL[300],
    "past_palette": [
        PRIMARY["default"],
        "#8E5A9E",
        SEMANTIC["warning"],
        SEMANTIC["error"],
        ROLE["manager"],
        ROLE["functional_owner"],
    ],
}

# --- Typography ------------------------------------------------------------
# Compact scale per the design system: 12/14/16/18/20/24px. Hierarchy
# comes from size + weight + color/lightness, not from an ever-growing
# set of font sizes.
FONT_SIZE = {
    "xs": "12px",
    "sm": "14px",
    "base": "16px",
    "lg": "18px",
    "xl": "20px",
    "xxl": "24px",
}
FONT_WEIGHT = {
    "regular": 400,
    "medium": 500,
    "semibold": 600,
    "bold": 700,
    "heavy": 800,
}
LINE_HEIGHT = {
    "tight": 1.2,
    "normal": 1.45,
    "relaxed": 1.6,
}
FONT_FAMILY = {
    "heading": '"Libre Franklin", "Source Sans 3", sans-serif',
    "body": (
        '"Source Sans 3", -apple-system, BlinkMacSystemFont, "Segoe UI", '
        "Roboto, Helvetica, Arial, sans-serif"
    ),
}

# --- Spacing ---------------------------------------------------------------
# A single scale used for padding/margin/gap everywhere, rem-based.
SPACE = {
    "3xs": "2px",
    "2xs": "4px",
    "xs": "6px",
    "sm": "8px",
    "md": "12px",
    "lg": "16px",
    "xl": "20px",
    "2xl": "28px",
    "3xl": "40px",
}

# --- Radius ------------------------------------------------------------
RADIUS = {
    "sm": "6px",
    "md": "8px",
    "lg": "12px",
    "pill": "999px",
    "circle": "50%",
}

# --- Elevation / shadow -----------------------------------------------
# Layered depth per the design doc: a default resting card, a
# hover/prominent card, and a recessed (inset) surface. Never one heavy
# shadow reused everywhere.
SHADOW = {
    "resting": "0 1px 2px rgba(27,34,51,0.04), 0 6px 20px rgba(27,34,51,0.06)",
    "hover": "0 2px 4px rgba(27,34,51,0.07), 0 12px 28px rgba(27,34,51,0.10)",
    "recessed": "inset 0 1px 2px rgba(27,34,51,0.08)",
}

# --- Motion -----------------------------------------------------------
# Small, purposeful transitions only (hover/focus feedback) — nothing
# animates layout-heavy properties like width/height/top/left.
TRANSITION = {
    "fast": "120ms ease-out",
    "base": "180ms ease-out",
}


@dataclass(frozen=True)
class Tokens:
    """Convenience bundle so callers can do `from tokens import TOKENS`
    and get everything through one object as well as by name."""

    neutral: dict = field(default_factory=lambda: NEUTRAL)
    primary: dict = field(default_factory=lambda: PRIMARY)
    semantic: dict = field(default_factory=lambda: SEMANTIC)
    role: dict = field(default_factory=lambda: ROLE)
    battery: dict = field(default_factory=lambda: BATTERY)
    font_size: dict = field(default_factory=lambda: FONT_SIZE)
    font_weight: dict = field(default_factory=lambda: FONT_WEIGHT)
    line_height: dict = field(default_factory=lambda: LINE_HEIGHT)
    font_family: dict = field(default_factory=lambda: FONT_FAMILY)
    space: dict = field(default_factory=lambda: SPACE)
    radius: dict = field(default_factory=lambda: RADIUS)
    shadow: dict = field(default_factory=lambda: SHADOW)
    transition: dict = field(default_factory=lambda: TRANSITION)


TOKENS = Tokens()
