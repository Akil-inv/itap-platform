from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Optional
from uuid import UUID

from ..clock import today
from ..domain import (
    Assignment,
    AssignmentNotFound,
    AssignmentState,
    ChangeRequest,
    ClosureRecord,
    ConcurrentModification,
    GoalSetting,
    RequestStatus,
    ReverseFeedback,
    ReviewScore,
)


class InMemoryAssignmentRepo:
    def __init__(self) -> None:
        self._assignments: dict[UUID, Assignment] = {}
        self._goal_settings: dict[UUID, GoalSetting] = {}  # keyed by assignment_id
        self._closure_records: dict[UUID, ClosureRecord] = {}  # keyed by assignment_id
        self._reverse_feedback: dict[UUID, list[ReverseFeedback]] = {}
        self._review_scores: dict[UUID, ReviewScore] = {}  # keyed by assignment_id
        self._change_requests: dict[UUID, ChangeRequest] = {}  # keyed by request id

    def add(self, assignment: Assignment) -> None:
        if assignment.id in self._assignments:
            raise ValueError(f"Assignment {assignment.id} already exists")
        self._assignments[assignment.id] = replace(assignment)

    def get(self, assignment_id: UUID) -> Assignment:
        try:
            # Return a copy: callers mutate freely, but a stale version
            # they hold won't silently overwrite a newer stored one —
            # update()/close_with_record() enforce that explicitly.
            return replace(self._assignments[assignment_id])
        except KeyError:
            raise AssignmentNotFound(assignment_id) from None

    def _write(self, assignment: Assignment) -> Assignment:
        current = self._assignments.get(assignment.id)
        if current is None:
            raise AssignmentNotFound(assignment.id)
        if current.version != assignment.version:
            raise ConcurrentModification(assignment.id)
        updated = replace(assignment, version=assignment.version + 1)
        self._assignments[assignment.id] = updated
        return updated

    def update(self, assignment: Assignment) -> None:
        self._write(assignment)

    def close_with_record(self, assignment: Assignment, closure: ClosureRecord) -> None:
        self._write(assignment)
        self._closure_records[closure.assignment_id] = closure

    def list_all(self) -> list[Assignment]:
        return [replace(a) for a in self._assignments.values()]

    def list_by_agent(self, agent_id: UUID) -> list[Assignment]:
        return [replace(a) for a in self._assignments.values() if a.agent_id == agent_id]

    def list_by_manager(self, manager_id: UUID) -> list[Assignment]:
        return [replace(a) for a in self._assignments.values() if a.manager_id == manager_id]

    def list_active_without_goal_setting(
        self, older_than_days: int, as_of: Optional[date] = None
    ) -> list[Assignment]:
        as_of = as_of or today()
        result = []
        for assignment in self._assignments.values():
            if assignment.state != AssignmentState.ACTIVE:
                continue
            if assignment.id in self._goal_settings:
                continue
            if (as_of - assignment.start_date).days >= older_than_days:
                result.append(replace(assignment))
        return result

    def list_active_older_than(
        self, older_than_days: int, as_of: Optional[date] = None
    ) -> list[Assignment]:
        as_of = as_of or today()
        return [
            replace(a)
            for a in self._assignments.values()
            if a.state == AssignmentState.ACTIVE
            and (as_of - a.start_date).days >= older_than_days
        ]

    def add_goal_setting(self, goal_setting: GoalSetting) -> None:
        self._goal_settings[goal_setting.assignment_id] = goal_setting

    def update_goal_setting(self, goal_setting: GoalSetting) -> None:
        self._goal_settings[goal_setting.assignment_id] = goal_setting

    def get_goal_setting(self, assignment_id: UUID) -> Optional[GoalSetting]:
        return self._goal_settings.get(assignment_id)

    def get_closure_record(self, assignment_id: UUID) -> Optional[ClosureRecord]:
        return self._closure_records.get(assignment_id)

    def add_reverse_feedback(self, feedback: ReverseFeedback) -> None:
        self._reverse_feedback.setdefault(feedback.assignment_id, []).append(feedback)

    def list_reverse_feedback(self, assignment_id: UUID) -> list[ReverseFeedback]:
        return list(self._reverse_feedback.get(assignment_id, []))

    # -- Review & Scoring (Phase 3) --

    def add_review_score(self, review_score: ReviewScore) -> None:
        self._review_scores[review_score.assignment_id] = review_score

    def update_review_score(self, review_score: ReviewScore) -> None:
        self._review_scores[review_score.assignment_id] = review_score

    def get_review_score(self, assignment_id: UUID) -> Optional[ReviewScore]:
        return self._review_scores.get(assignment_id)

    # -- Extension/Closure requests (Phase 3) --

    def add_change_request(self, request: ChangeRequest) -> None:
        self._change_requests[request.id] = request

    def update_change_request(self, request: ChangeRequest) -> None:
        self._change_requests[request.id] = request

    def get_change_request(self, request_id: UUID) -> Optional[ChangeRequest]:
        return self._change_requests.get(request_id)

    def list_change_requests(self, assignment_id: UUID) -> list[ChangeRequest]:
        return [r for r in self._change_requests.values() if r.assignment_id == assignment_id]

    def list_pending_change_requests(self) -> list[ChangeRequest]:
        return [r for r in self._change_requests.values() if r.status == RequestStatus.PENDING]
