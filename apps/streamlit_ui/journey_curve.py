"""The rotation-plan "journey curve": a winding, ascending path through a
plan's stages (not a straight timeline), with position(s) plotted on it —
one "you are here" marker for a single Agent, or one dot per Agent for an
Admin viewing a whole plan's cohort. Ported from the approved front-page
mockup (a standalone HTML/JS artifact, not part of this repo) into plain
Python + inline SVG, following the same zero-external-dependency,
st.iframe-rendered convention as org_tree.py.
"""
from __future__ import annotations

import html
from dataclasses import dataclass

import streamlit as st
from tokens import TOKENS

# Rendered inside an isolated st.iframe document (no access to the page's
# CSS custom properties), so raw token constants are imported directly
# from tokens.py rather than duplicated as local hex literals.
_TRACK_COLOR = TOKENS.neutral[300]
_TRAVELED_COLOR = TOKENS.role["manager"]
_PLAIN_COLOR = TOKENS.primary["default"]
_DONE_COLOR = TOKENS.semantic["success"]
_CURRENT_COLOR = TOKENS.role["manager"]
_UPCOMING_FILL = TOKENS.neutral[0]
_LABEL_COLOR = TOKENS.neutral[900]
_SUBLABEL_COLOR = TOKENS.neutral[500]

_WIDTH, _HEIGHT = 860, 210
_MARGIN_X, _MARGIN_Y = 70, 34
# Headroom above/below the curve's own y-range (_MARGIN_Y to
# _HEIGHT - _MARGIN_Y) for a stacked label + sub-label at the topmost or
# bottommost point — see render()'s viewBox comment.
_TOP_PAD, _BOTTOM_PAD = 40, 40


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


@dataclass
class _Point:
    x: float
    y: float


@dataclass
class _Segment:
    p0: _Point
    c1: _Point
    c2: _Point
    p1: _Point


def _lerp(a: _Point, b: _Point, t: float) -> _Point:
    return _Point(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)


def _bezier_point(seg: _Segment, t: float) -> _Point:
    mt = 1 - t
    x = mt**3 * seg.p0.x + 3 * mt**2 * t * seg.c1.x + 3 * mt * t**2 * seg.c2.x + t**3 * seg.p1.x
    y = mt**3 * seg.p0.y + 3 * mt**2 * t * seg.c1.y + 3 * mt * t**2 * seg.c2.y + t**3 * seg.p1.y
    return _Point(x, y)


def _split_left(seg: _Segment, t: float) -> _Segment:
    """De Casteljau subdivision — the sub-curve from 0..t of `seg`."""
    a = _lerp(seg.p0, seg.c1, t)
    b = _lerp(seg.c1, seg.c2, t)
    c = _lerp(seg.c2, seg.p1, t)
    d = _lerp(a, b, t)
    e = _lerp(b, c, t)
    f = _lerp(d, e, t)
    return _Segment(seg.p0, a, d, f)


class _Curve:
    def __init__(self, n: int) -> None:
        self.points: list[_Point] = []
        for i in range(n):
            x = _MARGIN_X if n == 1 else _MARGIN_X + i * (_WIDTH - 2 * _MARGIN_X) / (n - 1)
            rise = 0 if n == 1 else i * (_HEIGHT - 2 * _MARGIN_Y) / (n - 1)
            edge = 0 if 0 < i < n - 1 else 1
            wiggle = (12 if i % 2 == 0 else -12) * (1 - edge * 0.7)
            self.points.append(_Point(x, (_HEIGHT - _MARGIN_Y) - rise + wiggle))

        self.segments: list[_Segment] = []
        for s in range(n - 1):
            p0, p1 = self.points[s], self.points[s + 1]
            dx = p1.x - p0.x
            self.segments.append(
                _Segment(p0, _Point(p0.x + dx * 0.5, p0.y), _Point(p1.x - dx * 0.5, p1.y), p1)
            )

    def full_path_d(self) -> str:
        d = f"M {self.points[0].x:.1f},{self.points[0].y:.1f} "
        for seg in self.segments:
            d += (
                f"C {seg.c1.x:.1f},{seg.c1.y:.1f} {seg.c2.x:.1f},{seg.c2.y:.1f} "
                f"{seg.p1.x:.1f},{seg.p1.y:.1f} "
            )
        return d

    def traveled_path_d(self, progress: float) -> str:
        n = len(self.points)
        full = int(progress)
        t = progress - full
        if full >= n - 1:
            return self.full_path_d()
        d = f"M {self.points[0].x:.1f},{self.points[0].y:.1f} "
        for s in range(full):
            seg = self.segments[s]
            d += (
                f"C {seg.c1.x:.1f},{seg.c1.y:.1f} {seg.c2.x:.1f},{seg.c2.y:.1f} "
                f"{seg.p1.x:.1f},{seg.p1.y:.1f} "
            )
        if t > 0:
            sub = _split_left(self.segments[full], t)
            d += (
                f"C {sub.c1.x:.1f},{sub.c1.y:.1f} {sub.c2.x:.1f},{sub.c2.y:.1f} "
                f"{sub.p1.x:.1f},{sub.p1.y:.1f} "
            )
        return d

    def point_at(self, progress: float) -> _Point:
        n = len(self.points)
        if n == 1:
            return self.points[0]
        # progress == n-1 exactly (the current stage IS the last one — the
        # common case for a Portfolio's rotation timeline, unlike a
        # Rotation Plan's partway-through-a-stage progress) has no segment
        # of its own to interpolate within; return the last point directly
        # rather than letting the segment-index clamp below land one node
        # early (segments[n-2] at t=0 is points[n-2], not points[n-1]).
        if progress >= n - 1:
            return self.points[-1]
        full = max(int(progress), 0)
        t = max(0.0, min(1.0, progress - full))
        return _bezier_point(self.segments[full], t)


def render(
    stage_names: list[str],
    stage_subs: list[str] | None = None,
    progress: float | None = None,
    markers: list[dict] | None = None,
    height: int = 260,
) -> None:
    """Render the curve. Pass `progress` (a float 0..len(stages)-1, e.g.
    1.15 = partway into the second stage) for the single-traveler "you are
    here" view, or `markers` (a list of {"initial", "value", "color"}) to
    plot several people on one shared plan curve. `stage_subs` is an
    optional per-stage caption (e.g. the manager currently covering that
    stage)."""
    curve = _Curve(len(stage_names))
    stage_subs = stage_subs or [None] * len(stage_names)

    # `_TOP_PAD`/`_BOTTOM_PAD` give the viewBox real headroom above and
    # below the curve's own y-range (`_MARGIN_Y` to `_HEIGHT - _MARGIN_Y`)
    # for a stacked label + sub-label. The old viewBox only padded the
    # bottom (`_HEIGHT + 40`, for an odd-indexed point near the bottom
    # whose labels draw *below* it) and had no matching pad above y=0 —
    # so the topmost point, when it landed on an even index (labels draw
    # *above* it), could place its sub-label's baseline at y<10, close
    # enough to 0 that the glyphs' ascenders crossed y=0 and got clipped
    # by the SVG viewport itself. This is independent of the surrounding
    # iframe/CSS sizing — an SVG always clips to its own viewBox — so no
    # amount of iframe height would have fixed it on its own.
    #
    # Taller padding also means the viewBox's own aspect ratio no longer
    # matches what each call site's `height=` was tuned for, so
    # `height:100%` (with `html,body{height:100%}` so the percentage
    # resolves against something) fits the whole viewBox inside whatever
    # pixel box the iframe actually has, via the SVG's default
    # `preserveAspectRatio="xMidYMid meet"` — letterboxing if the two
    # aspect ratios don't match exactly, but never cropping regardless of
    # what `height` a caller passes.
    view_height = _HEIGHT + _TOP_PAD + _BOTTOM_PAD
    svg = [
        "<style>html,body{margin:0;height:100%;}</style>",
        f'<svg viewBox="0 {-_TOP_PAD} {_WIDTH} {view_height}" xmlns="http://www.w3.org/2000/svg" ',
    ]
    svg.append(
        'style="display:block; width:100%; height:100%; '
        'font-family:-apple-system,Segoe UI,Helvetica,sans-serif;">'
    )

    if progress is not None:
        svg.append(
            f'<path d="{curve.full_path_d()}" fill="none" stroke="{_TRACK_COLOR}" '
            f'stroke-width="4" stroke-dasharray="1 9" stroke-linecap="round"/>'
        )
        svg.append(
            f'<path d="{curve.traveled_path_d(progress)}" fill="none" '
            f'stroke="{_TRAVELED_COLOR}" stroke-width="4" stroke-linecap="round"/>'
        )
    else:
        svg.append(
            f'<path d="{curve.full_path_d()}" fill="none" stroke="{_PLAIN_COLOR}" '
            f'stroke-width="4" stroke-linecap="round" opacity="0.5"/>'
        )

    for i, name in enumerate(stage_names):
        p = curve.points[i]
        if progress is not None:
            status = "done" if i < progress else ("current" if int(progress) == i else "upcoming")
        else:
            status = "plain"
        fill = {
            "done": _DONE_COLOR,
            "current": _CURRENT_COLOR,
            "upcoming": _UPCOMING_FILL,
            "plain": _PLAIN_COLOR,
        }[status]
        stroke = _TRACK_COLOR if status == "upcoming" else fill
        # sub_y clears the "you are here" marker's halo (radius 13,
        # centered on this same point when progress lands exactly on a
        # node) — the original -6 offset used to render the stage's
        # manager name on top of that halo. label_y stays close to the
        # viewBox's own top/bottom edge, so it can't move out any further
        # without the label itself getting clipped.
        label_y = p.y - 20 if i % 2 == 0 else p.y + 34
        sub_y = p.y - 34 if i % 2 == 0 else p.y + 49
        svg.append(
            f'<circle cx="{p.x:.1f}" cy="{p.y:.1f}" r="8" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="2"/>'
        )
        svg.append(
            f'<text x="{p.x:.1f}" y="{label_y:.1f}" text-anchor="middle" '
            f'font-size="12.5" font-weight="700" fill="{_LABEL_COLOR}">{_esc(name)}</text>'
        )
        if stage_subs[i]:
            svg.append(
                f'<text x="{p.x:.1f}" y="{sub_y:.1f}" text-anchor="middle" '
                f'font-size="11" fill="{_SUBLABEL_COLOR}">{_esc(stage_subs[i])}</text>'
            )

    if progress is not None:
        me = curve.point_at(progress)
        svg.append(f'<circle cx="{me.x:.1f}" cy="{me.y:.1f}" r="13" fill="{_CURRENT_COLOR}" opacity="0.18"/>')
        svg.append(
            f'<circle cx="{me.x:.1f}" cy="{me.y:.1f}" r="6.5" fill="{_CURRENT_COLOR}" '
            f'stroke="{TOKENS.neutral[0]}" stroke-width="2.5"/>'
        )
        # The marker can land right on top of a stage node (progress==0, or
        # a stage with no target duration) — place "You are here" on the
        # opposite side from that node's own label/sub-label, not always
        # above, or the two collide illegibly.
        nearest_stage = min(int(round(progress)), len(stage_names) - 1)
        label_above = nearest_stage % 2 == 0
        you_are_here_y = me.y + 20 if label_above else me.y - 20
        svg.append(
            f'<text x="{me.x:.1f}" y="{you_are_here_y:.1f}" text-anchor="middle" '
            f'font-size="11" font-weight="700" fill="{_CURRENT_COLOR}">You are here</text>'
        )

    if markers:
        for m in markers:
            pt = curve.point_at(m["value"])
            color = _esc(m.get("color", _PLAIN_COLOR))
            initial = _esc(str(m.get("initial", "?")))
            svg.append(
                f'<circle cx="{pt.x:.1f}" cy="{pt.y + 16:.1f}" r="9" fill="{color}" '
                f'stroke="#FFFFFF" stroke-width="2"/>'
            )
            svg.append(
                f'<text x="{pt.x:.1f}" y="{pt.y + 30:.1f}" text-anchor="middle" '
                f'font-size="9.5" font-weight="700" fill="white">{initial}</text>'
            )

    svg.append("</svg>")
    st.iframe("".join(svg), height=height)
