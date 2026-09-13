"""In-app user manual — a "How to use ITAP" reference shown from the
persistent header (see app.py), content-scoped to the signed-in
person's own role (rbac_scope.Role) so an Associate never sees Admin
instructions and vice versa.

Deliberately built into the app rather than linking out to an external
docs site: this deployment already has to run fully air-gapped inside
CML (see offline_deploy/), so an external link would be one more thing
that's unreachable from inside the box. Editing the manual is editing
this file (plain markdown strings below) — no separate docs pipeline to
keep in sync.
"""
from __future__ import annotations

import streamlit as st
from rbac_scope import Role

_FUNCTIONAL_OWNER_MANUAL = """
### ITAP Admin — Workforce Overview

- **Associates** — every Associate, one row each: current team, a
  tenure bar, and a status filter (Active / Needs Attention / etc.).
  Click a name to open their full portfolio (profile, history, scores).
- **Org Structure** — the reporting tree of Managers and Functional
  Owners.
- **Onboard & Assign** — add a new Associate, Manager, or Functional
  Owner, and assign an Associate to a Manager (Primary / Secondary /
  CCA).
- **Setup** — one-off configuration (rotation catalog, kinds, etc.).
- **Approvals** — review and approve/deny pending manager requests.
- **Rotation Plans** — build and preview a rotation curve across
  several Associates at once.
- **Bulk Setup** — upload a Setup Workbook (.xlsx) to onboard many
  people and assignments in one go. Use **Download demo dataset** on
  the sign-in page first if you want to try the flow before using real
  data — same upload path either way.
- **Overdue** — Associates with an overdue goal-setting or episode
  closure.
- **Manager Handoff** — reassign an Associate from one Manager to
  another.
- **Consolidated Scores** — roll-up scoring view across the team.

**Tip:** an aggregate score is hidden behind an eye icon everywhere in
this view — click it to reveal, per Associate, one at a time.
"""

_MANAGER_MANUAL = """
### Line Manager — My Team

- **Current** tab — every Associate currently tasked to you (Primary,
  Secondary, or CCA). Click a name to open their page: goals, journey
  stepper, and your own review & scoring for the current episode.
- **Rolled Off** tab — read-only history of Associates who have since
  moved to a different manager.
- **Goals** — set or view the goal-setting text for an Associate's
  current episode. Once you freeze it, the Associate can no longer edit
  their own copy.
- **Review & Scoring** — score an episode. Scores you give are visible
  to you and to the Associate's own aggregate — never surfaced as a
  number to other managers.

**Note:** you won't see a rolled-up aggregate score for your team here
— that's an Admin-only view (Consolidated Scores). What you score stays
attached to the specific episode you scored.
"""

_AGENT_MANUAL = """
### Associate — My Journey

- **Profile** — your bio, photo, experience, and skills. Skills you add
  yourself are always marked self-reported; skills tied to a specific
  engagement are added by your manager or admin, not you.
- **My Progress** — your rotation plan preview, your own aggregate
  score (visible to no one but you), and a history of past episode
  scores.
- **Current Episode(s)** — one card per active assignment, with a
  journey stepper showing where it stands. Before your manager freezes
  goal-setting, you can edit the goal text yourself; once frozen, it's
  read-only.
- **Leave & Interests** — log upcoming leave dates (informational only,
  no approval needed) and flag interest in a Team or CCA — this is a
  standing signal to your manager/admin, not a placement request.

**Note:** only you can see your own aggregate score. No one else's
score is visible to you either.
"""

_MANUAL_BY_ROLE = {
    Role.FUNCTIONAL_OWNER: _FUNCTIONAL_OWNER_MANUAL,
    Role.MANAGER: _MANAGER_MANUAL,
    Role.AGENT: _AGENT_MANUAL,
}


def render(role: Role) -> None:
    """Renders the manual for `role` inside whatever container this is
    called under (a popover, in app.py's header)."""
    st.markdown(_MANUAL_BY_ROLE[role])
