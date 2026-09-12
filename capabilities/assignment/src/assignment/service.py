"""Application service: the one place that orchestrates rule evaluation
and persistence together. Screens (Streamlit) call this, never the repo
or the RuleEngine directly.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from .clock import today
from .domain import (
    Assignment,
    ClosureRecord,
    DuplicateAssignment,
    GoalSetting,
    ReverseFeedback,
)
from .ports import AssignmentRepo
from .rules import RuleEngine, TransitionDenied
from .rules_config import default_transition_table, guard_min_elapsed


class AssignmentService:
    def __init__(self, repo: AssignmentRepo, min_days_before_closure: int = 30):
        self._repo = repo
        self._min_days_before_closure = min_days_before_closure
        self._engine = RuleEngine(default_transition_table(min_days_before_closure))

    def create_assignment(
        self,
        agent_id: UUID,
        manager_id: UUID,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> Assignment:
        existing = self._repo.list_by_agent(agent_id)
        for a in existing:
            if a.manager_id == manager_id and a.state.value == "active":
                raise DuplicateAssignment(agent_id, manager_id)

        assignment = Assignment(
            agent_id=agent_id,
            manager_id=manager_id,
            start_date=start_date,
            end_date=end_date,
        )
        self._repo.add(assignment)
        return assignment

    def record_goal_setting(self, assignment_id: UUID, goals: str) -> GoalSetting:
        self._repo.get(assignment_id)  # raises AssignmentNotFound if missing
        goal_setting = GoalSetting(assignment_id=assignment_id, goals=goals)
        self._repo.add_goal_setting(goal_setting)
        return goal_setting

    def request_extension(
        self, assignment_id: UUID, requested_by: UUID, new_end_date: date
    ) -> Assignment:
        assignment = self._repo.get(assignment_id)
        self._engine.apply(
            assignment,
            "extension_requested",
            {"requested_by": requested_by, "new_end_date": new_end_date},
        )
        assignment.end_date = new_end_date
        self._repo.update(assignment)
        return assignment

    def close_assignment(
        self,
        assignment_id: UUID,
        objective_score: float,
        subjective_notes: str,
        reason: str = "completed",
        as_of: Optional[date] = None,
    ) -> Assignment:
        assignment = self._repo.get(assignment_id)
        has_goal_setting = self._repo.get_goal_setting(assignment_id) is not None
        closure = ClosureRecord(
            assignment_id=assignment_id,
            objective_score=objective_score,
            subjective_notes=subjective_notes,
        )
        ctx: dict = {"closure": closure, "has_goal_setting": has_goal_setting}
        if as_of is not None:
            ctx["as_of"] = as_of
        self._engine.apply(assignment, "close_requested", ctx)
        assignment.closed_reason = reason
        self._repo.close_with_record(assignment, closure)
        return assignment

    def close_administratively(
        self, assignment_id: UUID, reason: str, notes: Optional[str] = None
    ) -> Assignment:
        """Withdrawal or manager-departure closure: no score required, not
        gated by minimum-elapsed or goal-setting — these are
        administrative events, not performance assessments."""
        assignment = self._repo.get(assignment_id)
        self._engine.apply(assignment, "administrative_close", {})
        assignment.closed_reason = reason
        assignment.closure_note = notes
        self._repo.update(assignment)
        return assignment

    def withdraw_assignment(self, assignment_id: UUID, notes: Optional[str] = None) -> Assignment:
        """The Agent left the program (or this rotation) early. Distinct
        from close_assignment: no fabricated performance score."""
        return self.close_administratively(assignment_id, reason="withdrawn", notes=notes)

    def reassign_all_from_departing_manager(
        self,
        old_manager_id: UUID,
        new_manager_id: UUID,
        notes: Optional[str] = None,
        as_of: Optional[date] = None,
    ) -> list[Assignment]:
        """The Manager is leaving. Close every one of their active
        Assignments (reason="manager_departed", no score required) and
        open a fresh Assignment for each Agent under the new manager,
        starting today (or `as_of`)."""
        if old_manager_id == new_manager_id:
            raise ValueError("new_manager_id must differ from the departing manager")

        start = as_of or today()
        new_assignments = []
        for assignment in self._repo.list_by_manager(old_manager_id):
            if assignment.state.value != "active":
                continue
            self.close_administratively(assignment.id, reason="manager_departed", notes=notes)
            new_assignments.append(
                self.create_assignment(
                    agent_id=assignment.agent_id,
                    manager_id=new_manager_id,
                    start_date=start,
                )
            )
        return new_assignments

    def record_reverse_feedback(
        self, assignment_id: UUID, notes: str, as_of: Optional[date] = None
    ) -> ReverseFeedback:
        assignment = self._repo.get(assignment_id)
        allowed, reason = guard_min_elapsed(
            self._min_days_before_closure, assignment, {"as_of": as_of} if as_of else {}
        )
        if not allowed:
            raise TransitionDenied(reason)
        feedback = ReverseFeedback(assignment_id=assignment_id, notes=notes)
        self._repo.add_reverse_feedback(feedback)
        return feedback

    def list_overdue_goal_setting(
        self, older_than_days: int, as_of: Optional[date] = None
    ) -> list[Assignment]:
        return self._repo.list_active_without_goal_setting(older_than_days, as_of=as_of)

    def list_overdue_closure(
        self, older_than_days: Optional[int] = None, as_of: Optional[date] = None
    ) -> list[Assignment]:
        """Assignments that are past the point they could have been
        closed and still aren't — a Manager who never got around to it.
        Defaults the threshold to double the minimum-elapsed period."""
        threshold = older_than_days if older_than_days is not None else self._min_days_before_closure * 2
        return self._repo.list_active_older_than(threshold, as_of=as_of)
