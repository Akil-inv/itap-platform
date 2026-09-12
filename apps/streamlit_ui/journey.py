"""Maps an Assignment's real domain state (AssignmentState + whether a
GoalSetting exists) onto a 3-stage journey for display. This is a pure
presentation-layer read of the State pattern already implemented in
capabilities/assignment — it does not introduce new states, it only
renders the existing ones as a journey instead of a flat form dump.
"""
from __future__ import annotations

import streamlit as st

STAGES = ["Goal Setting", "Active", "Closed"]


def stage_index(assignment, goal_setting) -> int:
    if assignment.state.value == "closed":
        return 2
    if goal_setting is None:
        return 0
    return 1


def render_stepper(current: int) -> None:
    parts = ['<div class="itap-stepper">']
    for i, label in enumerate(STAGES):
        if i < current:
            step_class, line_class = "itap-step-done", "itap-step-line-done"
            marker = "✓"
        elif i == current:
            step_class, line_class = "itap-step-current", "itap-step-line-upcoming"
            marker = str(i + 1)
        else:
            step_class, line_class = "itap-step-upcoming", "itap-step-line-upcoming"
            marker = str(i + 1)

        parts.append(
            f'<div class="itap-step {step_class}">'
            f'<div class="itap-step-circle">{marker}</div>'
            f'<div class="itap-step-label">{label}</div>'
            f"</div>"
        )
        if i < len(STAGES) - 1:
            parts.append(f'<div class="itap-step-line {line_class}"></div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)
