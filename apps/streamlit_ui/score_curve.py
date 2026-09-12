"""The associate's own "learning curve": score milestones plotted as an
ascending/descending line with a dot per closed episode, replacing an
earlier plain st.bar_chart that rendered in Streamlit's default blue and
didn't match the rest of the token-driven design. Plain inline SVG via
st.markdown (same convention as battery.py) — simple enough it doesn't
need journey_curve.py's isolated st.iframe treatment.
"""
from __future__ import annotations

import html
from typing import TypedDict

from tokens import TOKENS

_WIDTH, _HEIGHT = 640, 200
_MARGIN_X, _MARGIN_Y = 36, 34
_LINE_COLOR = TOKENS.role["agent"]
_DOT_FILL = TOKENS.neutral[0]
_LABEL_COLOR = TOKENS.neutral[900]
_SUBLABEL_COLOR = TOKENS.neutral[500]
_GRID_COLOR = TOKENS.neutral[150]


class Milestone(TypedDict):
    score: float
    label: str


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_html(milestones: list[Milestone], max_score: float = 5.0) -> str:
    """Renders the score curve as an HTML fragment — use with
    st.markdown(..., unsafe_allow_html=True). Empty string if there are
    no milestones to plot (caller should show its own empty state)."""
    if not milestones:
        return ""

    plot_w = _WIDTH - 2 * _MARGIN_X
    plot_h = _HEIGHT - 2 * _MARGIN_Y
    n = len(milestones)

    def point(i: int, score: float) -> tuple[float, float]:
        x = _MARGIN_X if n == 1 else _MARGIN_X + (plot_w * i / (n - 1))
        y = _MARGIN_Y + plot_h * (1 - min(score, max_score) / max_score)
        return x, y

    points = [point(i, m["score"]) for i, m in enumerate(milestones)]

    parts = [
        f'<svg viewBox="0 0 {_WIDTH} {_HEIGHT}" width="100%" '
        f'style="max-width:{_WIDTH}px; overflow:visible; display:block;">'
    ]

    # Baseline grid (0 and max_score reference lines).
    top_y = _MARGIN_Y
    bottom_y = _MARGIN_Y + plot_h
    parts.append(
        f'<line x1="{_MARGIN_X}" y1="{bottom_y}" x2="{_WIDTH - _MARGIN_X}" y2="{bottom_y}" '
        f'stroke="{_GRID_COLOR}" stroke-width="1"></line>'
    )
    parts.append(
        f'<line x1="{_MARGIN_X}" y1="{top_y}" x2="{_WIDTH - _MARGIN_X}" y2="{top_y}" '
        f'stroke="{_GRID_COLOR}" stroke-width="1" stroke-dasharray="3,4"></line>'
    )

    # The curve itself: a smooth path through the points (or a single
    # dot with no line when there's only one milestone).
    if n > 1:
        path = f"M {points[0][0]:.1f} {points[0][1]:.1f} "
        for i in range(1, n):
            x0, y0 = points[i - 1]
            x1, y1 = points[i]
            mid_x = (x0 + x1) / 2
            path += f"C {mid_x:.1f} {y0:.1f}, {mid_x:.1f} {y1:.1f}, {x1:.1f} {y1:.1f} "
        parts.append(
            f'<path d="{path}" fill="none" stroke="{_LINE_COLOR}" '
            f'stroke-width="2.5" stroke-linecap="round"></path>'
        )

    for i, (x, y) in enumerate(points):
        m = milestones[i]
        is_last = i == n - 1
        r = 6 if is_last else 5
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{_DOT_FILL}" '
            f'stroke="{_LINE_COLOR}" stroke-width="{3 if is_last else 2.5}"></circle>'
        )
        score_label_y = max(y - 12, 12)
        parts.append(
            f'<text x="{x:.1f}" y="{score_label_y:.1f}" text-anchor="middle" '
            f'font-size="12" font-weight="700" fill="{_LABEL_COLOR}" '
            f'font-family="Source Sans 3, sans-serif">{m["score"]:.1f}</text>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{_HEIGHT - 8}" text-anchor="middle" '
            f'font-size="11" fill="{_SUBLABEL_COLOR}" '
            f'font-family="Source Sans 3, sans-serif">{_esc(m["label"])}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)
