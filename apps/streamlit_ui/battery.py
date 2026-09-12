"""Tenure "battery bar" for the Associates list (admin view) — per
docs/associate_journey_redesign.md's "Tenure battery bar" cross-cutting
rule: 1 segment = 3 months of *total* time in the system (not just the
current team), built from the Agent's PRIMARY-kind Assignment history
only (the spine that drives tenure, per spec — Secondary/CCA never
contribute a segment of their own). Green = the currently active
Primary's stint; every past Primary stint gets its own distinct color;
any stretch with no Primary active (before the first one, or a gap
between two) renders as a neutral gray segment — the clock keeps
running through it.

Segment count grows past 8 (2 years) rather than capping — the spec
leaves exact rendering past that point open ("TBD at mockup time"); this
keeps it simple by just keeps adding segments and letting them wrap via
flex-wrap in the CSS.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from assignment.domain import Assignment, AssignmentKind

SEGMENT_DAYS = 91  # ~3 months
CURRENT_COLOR = "#3F7D57"  # theme green
GAP_COLOR = "#D9DEE6"
PAST_STINT_PALETTE = ["#4C78A8", "#8E5A9E", "#B9791A", "#C0432F", "#16707F", "#333F6B"]


def primary_assignments(all_assignments: list[Assignment]) -> list[Assignment]:
    return sorted(
        (a for a in all_assignments if a.kind == AssignmentKind.PRIMARY),
        key=lambda a: a.start_date,
    )


def current_primary(primaries: list[Assignment]) -> Optional[Assignment]:
    active = [a for a in primaries if a.state.value == "active"]
    return active[-1] if active else None


def _covering_stint(mid: date, primaries: list[Assignment], today: date) -> Optional[Assignment]:
    for p in primaries:
        p_end = p.end_date or today
        if p.start_date <= mid <= p_end:
            return p
    return None


def build_segments(primaries: list[Assignment], today: Optional[date] = None) -> list[Optional[Assignment]]:
    """One entry per 3-month segment from the earliest Primary's start
    date through today: the Assignment covering that segment's midpoint,
    or None for a gap (no Primary active)."""
    if not primaries:
        return []
    today = today or date.today()
    earliest = primaries[0].start_date
    total_days = max((today - earliest).days, 1)
    n_segments = max(1, math.ceil(total_days / SEGMENT_DAYS))
    segments: list[Optional[Assignment]] = []
    for i in range(n_segments):
        seg_start = earliest + timedelta(days=i * SEGMENT_DAYS)
        seg_end = min(earliest + timedelta(days=(i + 1) * SEGMENT_DAYS), today)
        mid = seg_start + (seg_end - seg_start) / 2
        segments.append(_covering_stint(mid, primaries, today))
    return segments


def render_html(all_assignments: list[Assignment], today: Optional[date] = None) -> str:
    """Renders the battery bar as an HTML fragment (a row of colored
    divs) — use with st.markdown(..., unsafe_allow_html=True). Empty
    string if the Agent has never had a Primary Assignment."""
    primaries = primary_assignments(all_assignments)
    if not primaries:
        return ""
    today = today or date.today()
    segments = build_segments(primaries, today)
    current = current_primary(primaries)

    color_by_id: dict[UUID, str] = {}
    palette_idx = 0
    parts = ['<div class="itap-battery">']
    for seg in segments:
        if seg is None:
            color = GAP_COLOR
        elif current is not None and seg.id == current.id:
            color = CURRENT_COLOR
        else:
            if seg.id not in color_by_id:
                color_by_id[seg.id] = PAST_STINT_PALETTE[palette_idx % len(PAST_STINT_PALETTE)]
                palette_idx += 1
            color = color_by_id[seg.id]
        parts.append(f'<div class="itap-battery-seg" style="background-color:{color};"></div>')
    parts.append("</div>")
    return "".join(parts)
