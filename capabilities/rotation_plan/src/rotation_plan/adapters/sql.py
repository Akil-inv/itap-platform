"""SQL adapter, SQLAlchemy Core only — same conventions as
capabilities/assignment/adapters/sql.py: app-generated UUID keys, no
FK-constraint reliance, no autoincrement. `update_enrollment` enforces
optimistic concurrency the same way (`version` in the WHERE clause,
rowcount distinguishes "no such row" from "row exists but version moved").
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    insert,
    select,
    update,
)

from ..domain import (
    ConcurrentModification,
    Enrollment,
    EnrollmentNotFound,
    RotationPlan,
    RotationPlanNotFound,
)

metadata = MetaData()

rotation_plans_table = Table(
    "rotation_plans",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("stage_names", JSON, nullable=False),
    Column("weeks_per_stage", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

rotation_enrollments_table = Table(
    "rotation_enrollments",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("plan_id", String(36), nullable=False, index=True),
    Column("agent_id", String(36), nullable=False, index=True),
    Column("current_stage_index", Integer, nullable=False),
    Column("enrolled_at", DateTime(timezone=True), nullable=False),
    Column("stage_started_at", DateTime(timezone=True), nullable=False),
    Column("version", Integer, nullable=False),
)


def create_schema(engine: Engine) -> None:
    metadata.create_all(engine, tables=[rotation_plans_table, rotation_enrollments_table])


class SqlRotationPlanRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_plan(self, plan: RotationPlan) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(rotation_plans_table).values(
                    id=str(plan.id),
                    name=plan.name,
                    stage_names=plan.stage_names,
                    weeks_per_stage=plan.weeks_per_stage,
                    created_at=plan.created_at,
                )
            )

    def get_plan(self, plan_id: UUID) -> RotationPlan:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(rotation_plans_table).where(rotation_plans_table.c.id == str(plan_id))
            ).mappings().first()
        if row is None:
            raise RotationPlanNotFound(plan_id)
        return _row_to_plan(row)

    def list_plans(self) -> list[RotationPlan]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(rotation_plans_table)).mappings().all()
        return [_row_to_plan(r) for r in rows]

    def add_enrollment(self, enrollment: Enrollment) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(rotation_enrollments_table).values(**_enrollment_values(enrollment))
            )

    def get_enrollment(self, enrollment_id: UUID) -> Enrollment:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(rotation_enrollments_table).where(
                    rotation_enrollments_table.c.id == str(enrollment_id)
                )
            ).mappings().first()
        if row is None:
            raise EnrollmentNotFound(enrollment_id)
        return _row_to_enrollment(row)

    def get_enrollment_for_agent(
        self, agent_id: UUID, plan_id: UUID
    ) -> Optional[Enrollment]:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(rotation_enrollments_table).where(
                    rotation_enrollments_table.c.agent_id == str(agent_id),
                    rotation_enrollments_table.c.plan_id == str(plan_id),
                )
            ).mappings().first()
        return None if row is None else _row_to_enrollment(row)

    def list_enrollments_for_plan(self, plan_id: UUID) -> list[Enrollment]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(rotation_enrollments_table).where(
                    rotation_enrollments_table.c.plan_id == str(plan_id)
                )
            ).mappings().all()
        return [_row_to_enrollment(r) for r in rows]

    def list_enrollments_for_agent(self, agent_id: UUID) -> list[Enrollment]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(rotation_enrollments_table).where(
                    rotation_enrollments_table.c.agent_id == str(agent_id)
                )
            ).mappings().all()
        return [_row_to_enrollment(r) for r in rows]

    def update_enrollment(self, enrollment: Enrollment) -> None:
        with self._engine.begin() as conn:
            result = conn.execute(
                update(rotation_enrollments_table)
                .where(rotation_enrollments_table.c.id == str(enrollment.id))
                .where(rotation_enrollments_table.c.version == enrollment.version)
                .values(**_enrollment_values(enrollment, include_id=False, bump_version=True))
            )
            if result.rowcount == 0:
                exists = conn.execute(
                    select(rotation_enrollments_table.c.id).where(
                        rotation_enrollments_table.c.id == str(enrollment.id)
                    )
                ).first()
                if exists is None:
                    raise EnrollmentNotFound(enrollment.id)
                raise ConcurrentModification(enrollment.id)


def _enrollment_values(
    enrollment: Enrollment, include_id: bool = True, bump_version: bool = False
) -> dict:
    values = {
        "plan_id": str(enrollment.plan_id),
        "agent_id": str(enrollment.agent_id),
        "current_stage_index": enrollment.current_stage_index,
        "enrolled_at": enrollment.enrolled_at,
        "stage_started_at": enrollment.stage_started_at,
        "version": enrollment.version + 1 if bump_version else enrollment.version,
    }
    if include_id:
        values["id"] = str(enrollment.id)
    return values


def _row_to_plan(row) -> RotationPlan:
    return RotationPlan(
        id=UUID(row["id"]),
        name=row["name"],
        stage_names=list(row["stage_names"]),
        weeks_per_stage=row["weeks_per_stage"],
        created_at=row["created_at"],
    )


def _row_to_enrollment(row) -> Enrollment:
    return Enrollment(
        id=UUID(row["id"]),
        plan_id=UUID(row["plan_id"]),
        agent_id=UUID(row["agent_id"]),
        current_stage_index=row["current_stage_index"],
        enrolled_at=row["enrolled_at"],
        stage_started_at=row["stage_started_at"],
        version=row["version"],
    )
