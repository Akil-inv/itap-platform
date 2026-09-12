from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from .domain import Enrollment, RotationPlan


class RotationPlanRepo(Protocol):
    def add_plan(self, plan: RotationPlan) -> None: ...

    def get_plan(self, plan_id: UUID) -> RotationPlan: ...

    def list_plans(self) -> list[RotationPlan]: ...

    def update_plan(self, plan: RotationPlan) -> None:
        """Optimistic concurrency: `plan.version` must match the version
        currently stored, or this must raise ConcurrentModification
        without writing anything."""
        ...

    def add_enrollment(self, enrollment: Enrollment) -> None: ...

    def get_enrollment(self, enrollment_id: UUID) -> Enrollment: ...

    def get_enrollment_for_agent(
        self, agent_id: UUID, plan_id: UUID
    ) -> Optional[Enrollment]: ...

    def list_enrollments_for_plan(self, plan_id: UUID) -> list[Enrollment]: ...

    def list_enrollments_for_agent(self, agent_id: UUID) -> list[Enrollment]: ...

    def update_enrollment(self, enrollment: Enrollment) -> None:
        """Optimistic concurrency: `enrollment.version` must match the
        version currently stored, or this must raise
        ConcurrentModification without writing anything."""
        ...
