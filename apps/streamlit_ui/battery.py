"""Tenure "battery bar" for the Associates list (admin view) — per
docs/associate_journey_redesign.md's "Tenure battery bar" cross-cutting
rule: 1 segment = 3 months of *total* time in the system (not just the
current team), built from the Agent's PRIMARY-kind Assignment history
only (the spine that drives tenure, per spec — Secondary/CCA never
contribute a segment of their own). Green = the currently active
Primary's stint; any stretch with no Primary active (before the first
one, or a gap between two) renders as a neutral gray segment — the
clock keeps running through it.

Segment count grows past 8 (2 years) rather than capping — the spec
leaves exact rendering past that point open ("TBD at mockup time"); this
keeps it simple by just keeps adding segments and letting them wrap via
flex-wrap in the CSS.

**Past-stint color = the manager**, not "1st past stint, 2nd past
stint, ...": a color is derived deterministically from the manager's
party id (`_manager_color`), so the same manager's color is the same
everywhere it appears — on this Associate's bar, on every other
Associate's bar, and across any stint they return to that manager for.
Picking by arrival order instead (the original approach) meant the same
color could mean a different manager on every row, indistinguishable
from random without a legend. The tooltip spells out the manager name
and a months-of-tenure range regardless, so the color is a (collision-
prone, 6-color) skim aid on top of that, not the only cue.
"""
from __future__ import annotations

import html
import math
from datetime import date, timedelta
from uuid import UUID

from assignment.clock import today as clock_today
from assignment.domain import Assignment, AssignmentKind
from party_helpers import safe_get_name
from party_identity.ports import PartyRepo
from tokens import TOKENS

SEGMENT_DAYS = 91  # ~3 months
DAYS_PER_MONTH = 30
CURRENT_COLOR = TOKENS.battery["current"]
GAP_COLOR = TOKENS.battery["gap"]
PAST_STINT_PALETTE = TOKENS.battery["past_palette"]


def _manager_color(manager_id: UUID) -> str:
    return PAST_STINT_PALETTE[manager_id.int % len(PAST_STINT_PALETTE)]


def primary_assignments(all_assignments: list[Assignment]) -> list[Assignment]:
    return sorted(
        (a for a in all_assignments if a.kind == AssignmentKind.PRIMARY),
        key=lambda a: a.start_date,
    )


def current_primary(primaries: list[Assignment]) -> Assignment | None:
    active = [a for a in primaries if a.state.value == "active"]
    return active[-1] if active else None


def _covering_stint(mid: date, primaries: list[Assignment], today: date) -> Assignment | None:
    for p in primaries:
        p_end = p.end_date or today
        if p.start_date <= mid <= p_end:
            return p
    return None


def build_segments(primaries: list[Assignment], today: date | None = None) -> list[Assignment | None]:
    """One entry per 3-month segment from the earliest Primary's start
    date through today: the Assignment covering that segment's midpoint,
    or None for a gap (no Primary active)."""
    if not primaries:
        return []
    today = today or clock_today()
    earliest = primaries[0].start_date
    total_days = max((today - earliest).days, 1)
    n_segments = max(1, math.ceil(total_days / SEGMENT_DAYS))
    segments: list[Assignment | None] = []
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


def render_html(
    all_assignments: list[Assignment],
    party_repo: PartyRepo | None = None,
    today: date | None = None,
) -> str:
    """Renders the battery bar as an HTML fragment — a track/capsule
    ("meter") containing one colored segment per 3-month period, each
    with a `title` attribute (hover tooltip) giving the manager (when
    `party_repo` is passed — every current call site has one; it's
    optional only so this stays easy to unit-test without a repo), the
    calendar date range, and a running months-of-tenure count (e.g.
    "month 7-9 of tenure") rather than raw dates alone — a manager can
    picture "7-9 months in," not two ISO dates. Use with
    st.markdown(..., unsafe_allow_html=True). Empty string if the Agent
    has never had a Primary Assignment.

    Semantics are unchanged from before this pass: green = the current
    Primary's stint, gray/hatched = a gap with no Primary active. Past
    stints are colored by manager identity now, not arrival order — see
    this module's docstring. Only the rendered markup/CSS changed — see
    theme.py's `.itap-battery*` rules for the track styling."""
    primaries = primary_assignments(all_assignments)
    if not primaries:
        return ""
    today = today or clock_today()
    segments = build_segments(primaries, today)
    bounds = _segment_bounds(primaries, today)
    current = current_primary(primaries)

    parts = ['<div class="itap-battery-wrap"><div class="itap-battery">']
    cumulative_months = 0
    for seg, (seg_start, seg_end) in zip(segments, bounds):
        span_months = max(1, round((seg_end - seg_start).days / DAYS_PER_MONTH))
        month_range = f"month {cumulative_months + 1}-{cumulative_months + span_months} of tenure"
        cumulative_months += span_months
        date_range = f"{seg_start:%b %d, %Y} - {seg_end:%b %d, %Y}"

        if seg is None:
            title = html.escape(f"No active Primary · {date_range} · {month_range}")
            parts.append(f'<div class="itap-battery-seg itap-battery-seg--gap" title="{title}"></div>')
            continue

        manager_name = safe_get_name(party_repo, seg.manager_id) if party_repo else None
        manager_prefix = f"{manager_name} · " if manager_name else ""
        if current is not None and seg.id == current.id:
            color = CURRENT_COLOR
            title = html.escape(f"{manager_prefix}{date_range} · {month_range} · Current")
        else:
            color = _manager_color(seg.manager_id)
            title = html.escape(f"{manager_prefix}{date_range} · {month_range}")
        parts.append(
            f'<div class="itap-battery-seg" style="background-color:{color};" title="{title}"></div>'
        )
    parts.append('</div></div>')
    return "".join(parts)
