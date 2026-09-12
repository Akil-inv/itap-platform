"""Application service: the one place that orchestrates rule evaluation
and persistence together. Screens (Streamlit) call this, never the repo
or the RuleEngine directly.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from .domain import Assignment, ClosureRecord, GoalSetting, ReverseFeedback
from .ports import AssignmentRepo
from .rules import RuleEngine
from .rules_config import default_transition_table


class AssignmentService:
    def __init__(self, repo: AssignmentRepo, min_days_before_closure: int = 30):
        self._repo = repo
        self._engine = RuleEngine(default_transition_table(min_days_before_closure))

    def create_assignment(
        self,
        agent_id: UUID,
        manager_id: UUID,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> Assignment:
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
        closure = ClosureRecord(
            assignment_id=assignment_id,
            objective_score=objective_score,
            subjective_notes=subjective_notes,
        )
        ctx: dict = {"closure": closure}
        if as_of is not None:
            ctx["as_of"] = as_of
        self._engine.apply(assignment, "close_requested", ctx)
        assignment.closed_reason = reason
        self._repo.close_with_record(assignment, closure)
        return assignment

    def swap_to_new_manager(
        self,
        assignment_id: UUID,
        new_manager_id: UUID,
        objective_score: float,
        subjective_notes: str,
        new_start_date: date,
        new_end_date: Optional[date] = None,
        as_of: Optional[date] = None,
    ) -> Assignment:
        """Close the current Assignment (tenure complete) and open a new
        one under a different manager."""
        old = self._repo.get(assignment_id)
        self.close_assignment(
            assignment_id,
            objective_score,
            subjective_notes,
            reason="swapped",
            as_of=as_of,
        )
        return self.create_assignment(
            agent_id=old.agent_id,
            manager_id=new_manager_id,
            start_date=new_start_date,
            end_date=new_end_date,
        )

    def record_reverse_feedback(self, assignment_id: UUID, notes: str) -> ReverseFeedback:
        self._repo.get(assignment_id)
        feedback = ReverseFeedback(assignment_id=assignment_id, notes=notes)
        self._repo.add_reverse_feedback(feedback)
        return feedback

    def list_overdue_goal_setting(
        self, older_than_days: int, as_of: Optional[date] = None
    ) -> list[Assignment]:
        return self._repo.list_active_without_goal_setting(older_than_days, as_of=as_of)
