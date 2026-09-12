from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from .domain import AlreadyEnrolled, Enrollment, NoNextStage, RotationPlan, StageIndexOutOfRange
from .ports import RotationPlanRepo


def _as_utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip regardless of the column's
    `timezone=True` flag, so a datetime read back via the SQL adapter
    comes back naive even though it was always written as UTC. Treat any
    naive datetime as UTC rather than let arithmetic against an
    aware `datetime.now(timezone.utc)` raise."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class RotationPlanService:
    def __init__(self, repo: RotationPlanRepo) -> None:
        self._repo = repo

    def create_plan(
        self,
        name: str,
        stage_names: list[str],
        weeks_per_stage: int = 8,
        default_stage_managers: Optional[dict[int, UUID]] = None,
    ) -> RotationPlan:
        plan = RotationPlan(
            name=name,
            stage_names=list(stage_names),
            weeks_per_stage=weeks_per_stage,
            default_stage_managers=dict(default_stage_managers or {}),
        )
        self._repo.add_plan(plan)
        return plan

    def set_default_manager(
        self, plan_id: UUID, stage_index: int, manager_id: Optional[UUID]
    ) -> RotationPlan:
        """Set (or, with `manager_id=None`, clear) which Manager should
        get a new Assignment automatically when an Enrollment reaches
        `stage_index` (see `advance_stage`/the app layer's auto-advance
        bridge). Can be changed any time — it only affects future stage
        arrivals, not Enrollments already sitting on that stage."""
        plan = self._repo.get_plan(plan_id)
        if not (0 <= stage_index < plan.stage_count):
            raise StageIndexOutOfRange(stage_index)
        default_stage_managers = dict(plan.default_stage_managers)
        if manager_id is None:
            default_stage_managers.pop(stage_index, None)
        else:
            default_stage_managers[stage_index] = manager_id
        updated = replace(plan, default_stage_managers=default_stage_managers)
        self._repo.update_plan(updated)
        return self._repo.get_plan(plan_id)

    def enroll(
        self,
        plan_id: UUID,
        agent_id: UUID,
        as_of: Optional[datetime] = None,
        assignment_id: Optional[UUID] = None,
    ) -> Enrollment:
        self._repo.get_plan(plan_id)  # raises RotationPlanNotFound if missing
        if self._repo.get_enrollment_for_agent(agent_id, plan_id) is not None:
            raise AlreadyEnrolled(agent_id, plan_id)
        now = as_of or datetime.now(timezone.utc)
        stage_assignments = {0: assignment_id} if assignment_id is not None else {}
        enrollment = Enrollment(
            plan_id=plan_id,
            agent_id=agent_id,
            enrolled_at=now,
            stage_started_at=now,
            stage_assignments=stage_assignments,
        )
        self._repo.add_enrollment(enrollment)
        return enrollment

    def advance_stage(
        self,
        enrollment_id: UUID,
        as_of: Optional[datetime] = None,
        assignment_id: Optional[UUID] = None,
    ) -> Enrollment:
        enrollment = self._repo.get_enrollment(enrollment_id)
        plan = self._repo.get_plan(enrollment.plan_id)
        if enrollment.current_stage_index >= plan.stage_count - 1:
            raise NoNextStage(enrollment_id)
        now = as_of or datetime.now(timezone.utc)
        new_index = enrollment.current_stage_index + 1
        stage_assignments = dict(enrollment.stage_assignments)
        if assignment_id is not None:
            stage_assignments[new_index] = assignment_id
        updated = replace(
            enrollment,
            current_stage_index=new_index,
            stage_started_at=now,
            stage_assignments=stage_assignments,
        )
        self._repo.update_enrollment(updated)
        return self._repo.get_enrollment(enrollment_id)

    def link_assignment(
        self, enrollment_id: UUID, stage_index: int, assignment_id: UUID
    ) -> Enrollment:
        """Record which Assignment actually covers a given stage — by id
        only, since this package never imports `assignment`. Can target
        any valid stage, not just the current one, so a link made after
        the fact (or ahead of time) is just as easy as linking as you go."""
        enrollment = self._repo.get_enrollment(enrollment_id)
        plan = self._repo.get_plan(enrollment.plan_id)
        if not (0 <= stage_index < plan.stage_count):
            raise StageIndexOutOfRange(stage_index)
        stage_assignments = dict(enrollment.stage_assignments)
        stage_assignments[stage_index] = assignment_id
        updated = replace(enrollment, stage_assignments=stage_assignments)
        self._repo.update_enrollment(updated)
        return self._repo.get_enrollment(enrollment_id)

    def progress_value(
        self, enrollment: Enrollment, plan: RotationPlan, as_of: Optional[datetime] = None
    ) -> float:
        """Fractional position along the plan (for a "you are here" curve
        marker): the completed-stage count plus how far into the current
        stage's target duration we are. Clamped so a stage running long
        never visually reaches the next node — that's what advancing the
        stage is for."""
        now = as_of or datetime.now(timezone.utc)
        elapsed_days = (_as_utc(now) - _as_utc(enrollment.stage_started_at)).total_seconds() / 86400
        target_days = plan.weeks_per_stage * 7
        within_stage = max(0.0, min(0.98, elapsed_days / target_days)) if target_days > 0 else 0.0
        return enrollment.current_stage_index + within_stage
