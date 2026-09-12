"""RBAC layer over the Assignment aggregate.

Every visibility rule here is computed from the Viewer's relationship to
the record (assignment.manager_id / assignment.agent_id), not from a
separate per-role query implementation — this is the "computed from
relationships, not hardcoded per-role queries" requirement from
docs/architecture.md.

Child records (GoalSetting, ClosureRecord, ReverseFeedback) inherit their
parent Assignment's visibility: if you can see the Assignment, you can see
everything recorded against it. This is a deliberate simplification and
matches the spec — a Manager is meant to see reverse feedback given about
them on assignments they hold, an Agent is meant to see their own score.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from assignment.domain import Assignment, ClosureRecord, GoalSetting, ReverseFeedback
from assignment.ports import AssignmentRepo
from assignment.service import AssignmentService

from .domain import PermissionDenied, Role, Viewer


class ScopedAssignmentQueries:
    def __init__(self, repo: AssignmentRepo, service: AssignmentService):
        self._repo = repo
        self._service = service

    def _can_view(self, viewer: Viewer, assignment: Assignment) -> bool:
        if viewer.role == Role.FUNCTIONAL_OWNER:
            return True
        if viewer.role == Role.MANAGER:
            return assignment.manager_id == viewer.party_id
        if viewer.role == Role.AGENT:
            return assignment.agent_id == viewer.party_id
        return False

    def list_visible_assignments(self, viewer: Viewer) -> list[Assignment]:
        if viewer.role == Role.FUNCTIONAL_OWNER:
            return self._repo.list_all()
        if viewer.role == Role.MANAGER:
            return self._repo.list_by_manager(viewer.party_id)
        if viewer.role == Role.AGENT:
            return self._repo.list_by_agent(viewer.party_id)
        return []

    def get_assignment(self, viewer: Viewer, assignment_id: UUID) -> Assignment:
        assignment = self._repo.get(assignment_id)
        if not self._can_view(viewer, assignment):
            raise PermissionDenied(
                f"{viewer.role.value} {viewer.party_id} may not view assignment {assignment_id}"
            )
        return assignment

    def get_goal_setting(self, viewer: Viewer, assignment_id: UUID) -> Optional[GoalSetting]:
        self.get_assignment(viewer, assignment_id)
        return self._repo.get_goal_setting(assignment_id)

    def get_closure_record(self, viewer: Viewer, assignment_id: UUID) -> Optional[ClosureRecord]:
        self.get_assignment(viewer, assignment_id)
        return self._repo.get_closure_record(assignment_id)

    def list_reverse_feedback(
        self, viewer: Viewer, assignment_id: UUID
    ) -> list[ReverseFeedback]:
        self.get_assignment(viewer, assignment_id)
        return self._repo.list_reverse_feedback(assignment_id)

    def list_overdue_goal_setting(
        self, viewer: Viewer, older_than_days: int, as_of: Optional[date] = None
    ) -> list[Assignment]:
        if viewer.role == Role.AGENT:
            raise PermissionDenied("Agents may not query overdue goal-setting")
        overdue = self._service.list_overdue_goal_setting(older_than_days, as_of=as_of)
        if viewer.role == Role.FUNCTIONAL_OWNER:
            return overdue
        return [a for a in overdue if a.manager_id == viewer.party_id]

    def list_overdue_closure(
        self, viewer: Viewer, older_than_days: Optional[int] = None, as_of: Optional[date] = None
    ) -> list[Assignment]:
        if viewer.role == Role.AGENT:
            raise PermissionDenied("Agents may not query overdue closure")
        overdue = self._service.list_overdue_closure(older_than_days, as_of=as_of)
        if viewer.role == Role.FUNCTIONAL_OWNER:
            return overdue
        return [a for a in overdue if a.manager_id == viewer.party_id]

    def reassign_all_from_departing_manager(
        self,
        viewer: Viewer,
        old_manager_id: UUID,
        new_manager_id: UUID,
        notes: Optional[str] = None,
        as_of: Optional[date] = None,
    ) -> list[Assignment]:
        """Central-team-only: moving every one of a departing Manager's
        Agents is an organizational decision, not something a Manager
        (even the departing one) should trigger themselves."""
        if viewer.role != Role.FUNCTIONAL_OWNER:
            raise PermissionDenied("Only the Functional Owner may reassign a departing manager's team")
        return self._service.reassign_all_from_departing_manager(
            old_manager_id, new_manager_id, notes=notes, as_of=as_of
        )

    def consolidated_score(self, viewer: Viewer, agent_id: UUID) -> Optional[float]:
        """Average objective_score across every closed Assignment for one
        Agent. Functional Owner may query any Agent; an Agent may query
        only themselves; Managers do not get this view — their scope is
        deliberately limited to what pertains to their own assignments."""
        if viewer.role == Role.MANAGER:
            raise PermissionDenied("Managers may not view consolidated scores")
        if viewer.role == Role.AGENT and viewer.party_id != agent_id:
            raise PermissionDenied("Agents may only view their own consolidated score")

        scores = [
            record.objective_score
            for a in self._repo.list_by_agent(agent_id)
            if (record := self._repo.get_closure_record(a.id)) is not None
        ]
        return sum(scores) / len(scores) if scores else None
