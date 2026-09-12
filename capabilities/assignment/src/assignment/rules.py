"""A guarded state-transition table. Deliberately small: no action
registry, no external DSL. Guards decide whether a transition is allowed;
the calling service (see service.py) performs the actual field mutations
and persistence, so this module stays pure and trivially testable.

If this ever needs to become a Drools/DMN-backed engine, RuleEngine.apply
is the one seam to replace — nothing else in this package would change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .domain import Assignment, AssignmentState

GuardResult = tuple[bool, str | None]
Guard = Callable[[Assignment, dict], GuardResult]


@dataclass(frozen=True)
class TransitionRule:
    from_state: AssignmentState
    event: str
    guard: Guard
    to_state: AssignmentState


class TransitionDenied(Exception):
    pass


class RuleEngine:
    def __init__(self, rules: list[TransitionRule]):
        self._rules = rules

    def apply(self, assignment: Assignment, event: str, ctx: dict) -> None:
        """Mutates assignment.state in place if the transition is allowed;
        raises TransitionDenied otherwise. Does not persist anything."""
        candidates = [
            r for r in self._rules
            if r.from_state == assignment.state and r.event == event
        ]
        if not candidates:
            raise TransitionDenied(
                f"No transition defined for state={assignment.state.value!r} "
                f"event={event!r}"
            )
        rule = candidates[0]
        allowed, reason = rule.guard(assignment, ctx)
        if not allowed:
            raise TransitionDenied(reason or "Transition guard rejected the request")
        assignment.state = rule.to_state
