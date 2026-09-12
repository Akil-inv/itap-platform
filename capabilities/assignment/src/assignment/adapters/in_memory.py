from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from ..domain import (
    Assignment,
    AssignmentNotFound,
    AssignmentState,
    ClosureRecord,
    GoalSetting,
    ReverseFeedback,
)


class InMemoryAssignmentRepo:
    def __init__(self) -> None:
        self._assignments: dict[UUID, Assignment] = {}
        self._goal_settings: dict[UUID, GoalSetting] = {}  # keyed by assignment_id
        self._closure_records: dict[UUID, ClosureRecord] = {}  # keyed by assignment_id
        self._reverse_feedback: dict[UUID, list[ReverseFeedback]] = {}

    def add(self, assignment: Assignment) -> None:
        if assignment.id in self._assignments:
            raise ValueError(f"Assignment {assignment.id} already exists")
        self._assignments[assignment.id] = assignment

    def get(self, assignment_id: UUID) -> Assignment:
        try:
            return self._assignments[assignment_id]
        except KeyError:
            raise AssignmentNotFound(assignment_id) from None

    def update(self, assignment: Assignment) -> None:
        if assignment.id not in self._assignments:
            raise AssignmentNotFound(assignment.id)
        self._assignments[assignment.id] = assignment

    def close_with_record(self, assignment: Assignment, closure: ClosureRecord) -> None:
        if assignment.id not in self._assignments:
            raise AssignmentNotFound(assignment.id)
        self._assignments[assignment.id] = assignment
        self._closure_records[closure.assignment_id] = closure

    def list_by_agent(self, agent_id: UUID) -> list[Assignment]:
        return [a for a in self._assignments.values() if a.agent_id == agent_id]

    def list_by_manager(self, manager_id: UUID) -> list[Assignment]:
        return [a for a in self._assignments.values() if a.manager_id == manager_id]

    def list_active_without_goal_setting(
        self, older_than_days: int, as_of: Optional[date] = None
    ) -> list[Assignment]:
        as_of = as_of or date.today()
        result = []
        for assignment in self._assignments.values():
            if assignment.state != AssignmentState.ACTIVE:
                continue
            if assignment.id in self._goal_settings:
                continue
            if (as_of - assignment.start_date).days >= older_than_days:
                result.append(assignment)
        return result

    def add_goal_setting(self, goal_setting: GoalSetting) -> None:
        self._goal_settings[goal_setting.assignment_id] = goal_setting

    def get_goal_setting(self, assignment_id: UUID) -> Optional[GoalSetting]:
        return self._goal_settings.get(assignment_id)

    def get_closure_record(self, assignment_id: UUID) -> Optional[ClosureRecord]:
        return self._closure_records.get(assignment_id)

    def add_reverse_feedback(self, feedback: ReverseFeedback) -> None:
        self._reverse_feedback.setdefault(feedback.assignment_id, []).append(feedback)

    def list_reverse_feedback(self, assignment_id: UUID) -> list[ReverseFeedback]:
        return list(self._reverse_feedback.get(assignment_id, []))
