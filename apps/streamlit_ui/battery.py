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

import html
import math
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from assignment.domain import Assignment, AssignmentKind
from tokens import TOKENS

SEGMENT_DAYS = 91  # ~3 months
CURRENT_COLOR = TOKENS.battery["current"]
GAP_COLOR = TOKENS.battery["gap"]
PAST_STINT_PALETTE = TOKENS.battery["past_palette"]


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


def _segment_bounds(primaries: list[Assignment], today: date) -> list[tuple[date, date]]:
    """The (start, end) date range for each segment `build_segments`
    produces, in the same order — recomputed here rather than changed on
    `build_segments` itself (its date/segment math is unchanged; this
    just mirrors the same loop far enough to label each segment for the
    tooltip)."""
    if not primaries:
        return []
    earliest = primaries[0].start_date
    total_days = max((today - earliest).days, 1)
    n_segments = max(1, math.ceil(total_days / SEGMENT_DAYS))
    bounds = []
    for i in range(n_segments):
        seg_start = earliest + timedelta(days=i * SEGMENT_DAYS)
        seg_end = min(earliest + timedelta(days=(i + 1) * SEGMENT_DAYS), today)
        bounds.append((seg_start, seg_end))
    return bounds


def render_html(all_assignments: list[Assignment], today: Optional[date] = None) -> str:
    """Renders the battery bar as an HTML fragment — a track/capsule
    ("meter") containing one colored segment per 3-month period, each
    with a `title` attribute (hover tooltip) describing its date range
    and, for the current segment, that it's ongoing. Use with
    st.markdown(..., unsafe_allow_html=True). Empty string if the Agent
    has never had a Primary Assignment.

    Semantics are unchanged from before this pass: green = the current
    Primary's stint, a distinct color per past Primary stint, gray/hatched
    = a gap with no Primary active. Only the rendered markup/CSS changed —
    see theme.py's `.itap-battery*` rules for the track styling."""
    primaries = primary_assignments(all_assignments)
    if not primaries:
        return ""
    today = today or date.today()
    segments = build_segments(primaries, today)
    bounds = _segment_bounds(primaries, today)
    current = current_primary(primaries)

    color_by_id: dict[UUID, str] = {}
    palette_idx = 0
    parts = ['<div class="itap-battery-wrap"><div class="itap-battery">']
    for seg, (seg_start, seg_end) in zip(segments, bounds):
        if seg is None:
            title = html.escape(f"{seg_start.isoformat()} to {seg_end.isoformat()} — gap, no active Primary")
            parts.append(f'<div class="itap-battery-seg itap-battery-seg--gap" title="{title}"></div>')
            continue
        if current is not None and seg.id == current.id:
            color = CURRENT_COLOR
            title = html.escape(f"{seg_start.isoformat()} to {seg_end.isoformat()} — Current")
        else:
            if seg.id not in color_by_id:
                color_by_id[seg.id] = PAST_STINT_PALETTE[palette_idx % len(PAST_STINT_PALETTE)]
                palette_idx += 1
            color = color_by_id[seg.id]
            title = html.escape(f"{seg_start.isoformat()} to {seg_end.isoformat()}")
        parts.append(
            f'<div class="itap-battery-seg" style="background-color:{color};" title="{title}"></div>'
        )
    parts.append('</div></div>')
    return "".join(parts)
