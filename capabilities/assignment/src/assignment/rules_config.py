"""ITAP's concrete transition table and guard functions.

MVP defaults encoded here, called out explicitly so they're easy to find
and revisit:
  - Extension may only be requested by the assignment's own manager.
  - Closure requires both a minimum elapsed period (default 30 days,
    configurable) AND a closure record (objective_score + subjective_notes)
    supplied in the transition context.
"""
from __future__ import annotations

from datetime import date

from .domain import Assignment, AssignmentState
from .rules import Guard, GuardResult, TransitionRule


def guard_requested_by_manager(assignment: Assignment, ctx: dict) -> GuardResult:
    if ctx.get("requested_by") != assignment.manager_id:
        return False, "Only the assigned manager can request an extension"
    if "new_end_date" not in ctx:
        return False, "new_end_date is required to extend an assignment"
    return True, None


def make_min_elapsed_closure_guard(min_days: int) -> Guard:
    def guard(assignment: Assignment, ctx: dict) -> GuardResult:
        as_of = ctx.get("as_of", date.today())
        elapsed = (as_of - assignment.start_date).days
        if elapsed < min_days:
            return False, (
                f"Assignment must run at least {min_days} days before "
                f"closure (elapsed: {elapsed})"
            )
        if "closure" not in ctx:
            return False, (
                "A closure record (objective_score, subjective_notes) is "
                "required to close an assignment"
            )
        return True, None

    return guard


def default_transition_table(min_days_before_closure: int = 30) -> list[TransitionRule]:
    return [
        TransitionRule(
            from_state=AssignmentState.ACTIVE,
            event="extension_requested",
            guard=guard_requested_by_manager,
            to_state=AssignmentState.ACTIVE,
        ),
        TransitionRule(
            from_state=AssignmentState.ACTIVE,
            event="close_requested",
            guard=make_min_elapsed_closure_guard(min_days_before_closure),
            to_state=AssignmentState.CLOSED,
        ),
    ]
