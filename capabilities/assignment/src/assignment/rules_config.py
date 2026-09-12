"""ITAP's concrete transition table and guard functions.

MVP defaults encoded here, called out explicitly so they're easy to find
and revisit:
  - Extension may only be requested by the assignment's own manager, and
    the new end date must be later than the current one (an "extension"
    that shortens the assignment is a bug, not a feature).
  - Closure requires: a minimum elapsed period (default 30 days,
    configurable), a closure record (objective_score + subjective_notes)
    in the transition context, AND a GoalSetting already recorded —
    closing without goals would mean scoring against nothing.
  - Reverse feedback (Agent -> Manager) is gated by the same minimum
    elapsed period as closure — see guard_min_elapsed(), reused directly
    by AssignmentService.record_reverse_feedback rather than through
    RuleEngine, since feedback isn't a state transition.
  - "administrative_close" (withdrawal / manager departure) is NOT gated
    by the minimum-elapsed period or by goal-setting: these are
    administrative events, not performance assessments, and can happen
    at any point in the assignment's life.
"""
from __future__ import annotations

from .clock import today
from .domain import Assignment, AssignmentState
from .rules import Guard, GuardResult, TransitionRule


def guard_requested_by_manager(assignment: Assignment, ctx: dict) -> GuardResult:
    if ctx.get("requested_by") != assignment.manager_id:
        return False, "Only the assigned manager can request an extension"
    if "new_end_date" not in ctx:
        return False, "new_end_date is required to extend an assignment"
    new_end_date = ctx["new_end_date"]
    floor = assignment.end_date or assignment.start_date
    if new_end_date <= floor:
        return False, (
            f"An extension must move the end date later than {floor} "
            f"(got {new_end_date}) — to shorten an assignment, close it instead"
        )
    return True, None


def guard_min_elapsed(min_days: int, assignment: Assignment, ctx: dict) -> GuardResult:
    as_of = ctx.get("as_of", today())
    elapsed = (as_of - assignment.start_date).days
    if elapsed < min_days:
        return False, (
            f"Assignment must run at least {min_days} days before this "
            f"action (elapsed: {elapsed})"
        )
    return True, None


def make_min_elapsed_closure_guard(min_days: int) -> Guard:
    def guard(assignment: Assignment, ctx: dict) -> GuardResult:
        allowed, reason = guard_min_elapsed(min_days, assignment, ctx)
        if not allowed:
            return allowed, reason
        if not ctx.get("has_goal_setting"):
            return False, (
                "No goal setting has been recorded for this assignment — "
                "there is nothing to assess against. Record goal setting "
                "before closing."
            )
        if "closure" not in ctx:
            return False, (
                "A closure record (objective_score, subjective_notes) is "
                "required to close an assignment"
            )
        return True, None

    return guard


def guard_administrative_close(assignment: Assignment, ctx: dict) -> GuardResult:
    return True, None


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
        TransitionRule(
            from_state=AssignmentState.ACTIVE,
            event="administrative_close",
            guard=guard_administrative_close,
            to_state=AssignmentState.CLOSED,
        ),
    ]
