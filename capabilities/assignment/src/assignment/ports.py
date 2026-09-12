"""Port for the Assignment aggregate (Assignment + its child records:
GoalSetting, ClosureRecord, ReverseFeedback). Kept as one port because
these entities share one lifecycle and one root — splitting them into
separate repos would add indirection without a present need.
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Protocol
from uuid import UUID

from .domain import Assignment, ClosureRecord, GoalSetting, ReverseFeedback


class AssignmentRepo(Protocol):
    def add(self, assignment: Assignment) -> None: ...

    def get(self, assignment_id: UUID) -> Assignment: ...

    def update(self, assignment: Assignment) -> None:
        """Persist a state/field change that does not also write a child
        record (e.g. an extension). For closure, use close_with_record —
        that write spans two tables and must be atomic."""
        ...

    def close_with_record(self, assignment: Assignment, closure: ClosureRecord) -> None:
        """Atomically persist the assignment's CLOSED state and its
        ClosureRecord in one transaction."""
        ...

    def list_by_agent(self, agent_id: UUID) -> list[Assignment]: ...

    def list_by_manager(self, manager_id: UUID) -> list[Assignment]: ...

    def list_active_without_goal_setting(
        self, older_than_days: int, as_of: Optional[date] = None
    ) -> list[Assignment]:
        """Assignments still ACTIVE, started more than `older_than_days`
        ago, with no GoalSetting recorded — the feed a reminder job would
        poll."""
        ...

    def add_goal_setting(self, goal_setting: GoalSetting) -> None: ...

    def get_goal_setting(self, assignment_id: UUID) -> Optional[GoalSetting]: ...

    def get_closure_record(self, assignment_id: UUID) -> Optional[ClosureRecord]: ...

    def add_reverse_feedback(self, feedback: ReverseFeedback) -> None: ...

    def list_reverse_feedback(self, assignment_id: UUID) -> list[ReverseFeedback]: ...
