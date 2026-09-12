"""Port for the Assignment aggregate (Assignment + its child records:
GoalSetting, ClosureRecord, ReverseFeedback). Kept as one port because
these entities share one lifecycle and one root — splitting them into
separate repos would add indirection without a present need.
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Protocol
from uuid import UUID

from .domain import (
    Assignment,
    ChangeRequest,
    ClosureRecord,
    GoalSetting,
    ReverseFeedback,
    ReviewScore,
)


class AssignmentRepo(Protocol):
    def add(self, assignment: Assignment) -> None: ...

    def get(self, assignment_id: UUID) -> Assignment: ...

    def update(self, assignment: Assignment) -> None:
        """Persist a state/field change that does not also write a child
        record (e.g. an extension). For closure, use close_with_record —
        that write spans two tables and must be atomic.

        Optimistic concurrency: `assignment.version` must match the
        version currently stored, or this must raise
        ConcurrentModification without writing anything. Implementations
        persist the incremented version on success."""
        ...

    def close_with_record(self, assignment: Assignment, closure: ClosureRecord) -> None:
        """Atomically persist the assignment's CLOSED state and its
        ClosureRecord in one transaction. Same optimistic-concurrency
        contract as update()."""
        ...

    def list_all(self) -> list[Assignment]:
        """Every Assignment. Functional Owner's blanket-visibility need —
        used by the RBAC scope layer, not by manager/agent-facing code."""
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

    def list_active_older_than(
        self, older_than_days: int, as_of: Optional[date] = None
    ) -> list[Assignment]:
        """Every Assignment still ACTIVE, started more than
        `older_than_days` ago — regardless of goal-setting status. Used
        to build "overdue closure" (a Manager who never got around to
        scoring someone) on top of, with a larger threshold than the
        goal-setting reminder."""
        ...

    def add_goal_setting(self, goal_setting: GoalSetting) -> None: ...

    def update_goal_setting(self, goal_setting: GoalSetting) -> None:
        """Replace an existing GoalSetting's fields (goal text, criteria,
        freeze state) in place, keyed by assignment_id — used for both a
        pre-freeze text edit and the freeze/reopen actions themselves."""
        ...

    def get_goal_setting(self, assignment_id: UUID) -> Optional[GoalSetting]: ...

    def get_closure_record(self, assignment_id: UUID) -> Optional[ClosureRecord]: ...

    def add_reverse_feedback(self, feedback: ReverseFeedback) -> None: ...

    def list_reverse_feedback(self, assignment_id: UUID) -> list[ReverseFeedback]: ...

    # -- Review & Scoring (Phase 3) --

    def add_review_score(self, review_score: ReviewScore) -> None: ...

    def update_review_score(self, review_score: ReviewScore) -> None:
        """Replace an existing ReviewScore in place (re-submission after
        an admin reopen, or the reopen itself clearing `frozen`)."""
        ...

    def get_review_score(self, assignment_id: UUID) -> Optional[ReviewScore]: ...

    # -- Extension/Closure requests (Phase 3) --

    def add_change_request(self, request: ChangeRequest) -> None: ...

    def update_change_request(self, request: ChangeRequest) -> None: ...

    def get_change_request(self, request_id: UUID) -> Optional[ChangeRequest]: ...

    def list_change_requests(self, assignment_id: UUID) -> list[ChangeRequest]: ...

    def list_pending_change_requests(self) -> list[ChangeRequest]:
        """Every PENDING ChangeRequest, any assignment — the feed an
        admin-approval screen would list from. Not consumed by any UI
        yet (see ChangeRequest's docstring) but needed now so that
        screen doesn't require a repo change to add later."""
        ...
