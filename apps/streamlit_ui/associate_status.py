"""Status classification for the admin's Associates list filter chips
(Active / Needs attention / Available / Completed). The redesign spec
(docs/associate_journey_redesign.md) leaves the exact thresholds "TBD at
mockup time" — the rules below are this pass's judgment call, documented
here rather than buried in the view:

- **Active**: has an active Primary Assignment, nothing overdue.
- **Needs attention**: has an active Primary Assignment, but it shows up
  in the admin's existing "Overdue" queries (overdue goal-setting or
  overdue closure) — reusing those already-defined thresholds instead of
  inventing a new one keeps the two concepts in sync.
- **Available**: no active Primary right now, but the Agent is not
  considered fully done — either they're mid-gap between Primary stages
  (with or without an active Secondary/CCA keeping them busy), or they've
  never had a Primary at all yet ("unassigned").
- **Completed**: no active Assignment of *any* kind, AND their most
  recent Primary closed normally (`closed_reason == "completed"`) rather
  than being withdrawn or cut short — i.e. they finished their last
  rotation on the ordinary path and nothing else is in flight. A
  Primary that was withdrawn, or an Agent still holding an active
  Secondary/CCA, stays "Available" instead — there's still something
  live or unresolved about their record.
"""
from __future__ import annotations

from enum import Enum

from assignment.domain import Assignment, AssignmentKind
from battery import primary_assignments


class AssociateStatus(str, Enum):
    ACTIVE = "Active"
    NEEDS_ATTENTION = "Needs attention"
    AVAILABLE = "Available"
    COMPLETED = "Completed"


def classify(
    all_assignments: list[Assignment],
    overdue_assignment_ids: set,
) -> AssociateStatus:
    primaries = primary_assignments(all_assignments)
    active_primary = next((p for p in primaries if p.state.value == "active"), None)

    if active_primary is not None:
        if active_primary.id in overdue_assignment_ids:
            return AssociateStatus.NEEDS_ATTENTION
        return AssociateStatus.ACTIVE

    has_active_other = any(
        a.state.value == "active" and a.kind != AssignmentKind.PRIMARY for a in all_assignments
    )
    if has_active_other or not primaries:
        return AssociateStatus.AVAILABLE

    most_recent_primary = primaries[-1]
    if most_recent_primary.closed_reason == "completed":
        return AssociateStatus.COMPLETED
    return AssociateStatus.AVAILABLE


def current_team_label(services, all_assignments: list[Assignment]) -> str:
    primaries = primary_assignments(all_assignments)
    active_primary = next((p for p in primaries if p.state.value == "active"), None)
    if active_primary is not None:
        from party_helpers import safe_get_name

        return safe_get_name(services.party_repo, active_primary.manager_id)
    if primaries:
        return "Available"
    return "— unassigned —"
