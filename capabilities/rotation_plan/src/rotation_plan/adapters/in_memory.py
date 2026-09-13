from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from ..domain import (
    ConcurrentModification,
    Enrollment,
    EnrollmentNotFound,
    RotationPlan,
    RotationPlanNotFound,
)


def _copy_plan(p: RotationPlan) -> RotationPlan:
    return replace(
        p,
        stage_names=list(p.stage_names),
        default_stage_managers=dict(p.default_stage_managers),
    )


def _copy_enrollment(e: Enrollment) -> Enrollment:
    return replace(e, stage_assignments=dict(e.stage_assignments))


class InMemoryRotationPlanRepo:
    def __init__(self) -> None:
        self._plans: dict[UUID, RotationPlan] = {}
        self._enrollments: dict[UUID, Enrollment] = {}

    def add_plan(self, plan: RotationPlan) -> None:
        if plan.id in self._plans:
            raise ValueError(f"RotationPlan {plan.id} already exists")
        self._plans[plan.id] = _copy_plan(plan)

    def get_plan(self, plan_id: UUID) -> RotationPlan:
        try:
            plan = self._plans[plan_id]
        except KeyError:
            raise RotationPlanNotFound(plan_id) from None
        return _copy_plan(plan)

    def list_plans(self) -> list[RotationPlan]:
        return [_copy_plan(p) for p in self._plans.values()]

    def update_plan(self, plan: RotationPlan) -> None:
        current = self._plans.get(plan.id)
        if current is None:
            raise RotationPlanNotFound(plan.id)
        if current.version != plan.version:
            raise ConcurrentModification(plan.id)
        self._plans[plan.id] = _copy_plan(replace(plan, version=plan.version + 1))

    def add_enrollment(self, enrollment: Enrollment) -> None:
        if enrollment.id in self._enrollments:
            raise ValueError(f"Enrollment {enrollment.id} already exists")
        self._enrollments[enrollment.id] = _copy_enrollment(enrollment)

    def get_enrollment(self, enrollment_id: UUID) -> Enrollment:
        try:
            return _copy_enrollment(self._enrollments[enrollment_id])
        except KeyError:
            raise EnrollmentNotFound(enrollment_id) from None

    def get_enrollment_for_agent(
        self, agent_id: UUID, plan_id: UUID
    ) -> Enrollment | None:
        for e in self._enrollments.values():
            if e.agent_id == agent_id and e.plan_id == plan_id:
                return _copy_enrollment(e)
        return None

    def list_enrollments_for_plan(self, plan_id: UUID) -> list[Enrollment]:
        return [_copy_enrollment(e) for e in self._enrollments.values() if e.plan_id == plan_id]

    def list_enrollments_for_agent(self, agent_id: UUID) -> list[Enrollment]:
        return [_copy_enrollment(e) for e in self._enrollments.values() if e.agent_id == agent_id]

    def update_enrollment(self, enrollment: Enrollment) -> None:
        current = self._enrollments.get(enrollment.id)
        if current is None:
            raise EnrollmentNotFound(enrollment.id)
        if current.version != enrollment.version:
            raise ConcurrentModification(enrollment.id)
        self._enrollments[enrollment.id] = _copy_enrollment(
            replace(enrollment, version=enrollment.version + 1)
        )
