"""SQL adapter, SQLAlchemy Core only, same conventions as
capabilities/party_identity/adapters/sql.py: app-generated UUID keys, no
FK-constraint reliance, no autoincrement.

`close_with_record` is the one place this app currently needs a real
multi-table transaction (Assignment.state + ClosureRecord in one commit).
Postgres gives us that for free — take it while we have it. If this ever
moves to an Iceberg-backed adapter, this method is the one that would need
redesigning (e.g. via the outbox pattern), not the rest of the package.

`update`/`close_with_record` enforce optimistic concurrency: the WHERE
clause matches on `version` as well as `id`, so a write against a stale
copy affects zero rows — the code below distinguishes "no such row"
(AssignmentNotFound) from "row exists but version moved"
(ConcurrentModification) with one extra SELECT inside the same
transaction.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    JSON,
    Column,
    Connection,
    Date,
    DateTime,
    Engine,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    insert,
    select,
    update,
)

from ..clock import today
from ..domain import (
    Assignment,
    AssignmentNotFound,
    AssignmentState,
    ClosureRecord,
    ConcurrentModification,
    GoalSetting,
    ReverseFeedback,
)

metadata = MetaData()

assignments_table = Table(
    "assignments",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("agent_id", String(36), nullable=False, index=True),
    Column("manager_id", String(36), nullable=False, index=True),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=True),
    Column("state", String(32), nullable=False),
    Column("closed_reason", String(32), nullable=True),
    Column("closure_note", Text, nullable=True),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

goal_settings_table = Table(
    "goal_settings",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("assignment_id", String(36), nullable=False, unique=True, index=True),
    Column("goals", Text, nullable=False),
    Column("criteria", JSON, nullable=False, default=list),
    Column("set_at", DateTime(timezone=True), nullable=False),
)

closure_records_table = Table(
    "closure_records",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("assignment_id", String(36), nullable=False, unique=True, index=True),
    Column("objective_score", Float, nullable=False),
    Column("subjective_notes", Text, nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
)

reverse_feedback_table = Table(
    "reverse_feedback",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("assignment_id", String(36), nullable=False, index=True),
    Column("notes", Text, nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
)


def create_schema(engine: Engine) -> None:
    metadata.create_all(
        engine,
        tables=[
            assignments_table,
            goal_settings_table,
            closure_records_table,
            reverse_feedback_table,
        ],
    )


class SqlAssignmentRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, assignment: Assignment) -> None:
        with self._engine.begin() as conn:
            conn.execute(insert(assignments_table).values(**_assignment_values(assignment)))

    def get(self, assignment_id: UUID) -> Assignment:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(assignments_table).where(assignments_table.c.id == str(assignment_id))
            ).mappings().first()
        if row is None:
            raise AssignmentNotFound(assignment_id)
        return _row_to_assignment(row)

    def _write(self, conn: Connection, assignment: Assignment) -> None:
        result = conn.execute(
            update(assignments_table)
            .where(assignments_table.c.id == str(assignment.id))
            .where(assignments_table.c.version == assignment.version)
            .values(**_assignment_values(assignment, include_id=False, bump_version=True))
        )
        if result.rowcount == 0:
            exists = conn.execute(
                select(assignments_table.c.id).where(
                    assignments_table.c.id == str(assignment.id)
                )
            ).first()
            if exists is None:
                raise AssignmentNotFound(assignment.id)
            raise ConcurrentModification(assignment.id)

    def update(self, assignment: Assignment) -> None:
        with self._engine.begin() as conn:
            self._write(conn, assignment)

    def close_with_record(self, assignment: Assignment, closure: ClosureRecord) -> None:
        with self._engine.begin() as conn:
            self._write(conn, assignment)
            conn.execute(
                insert(closure_records_table).values(
                    id=str(closure.id),
                    assignment_id=str(closure.assignment_id),
                    objective_score=closure.objective_score,
                    subjective_notes=closure.subjective_notes,
                    recorded_at=closure.recorded_at,
                )
            )

    def list_all(self) -> list[Assignment]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(assignments_table)).mappings().all()
        return [_row_to_assignment(r) for r in rows]

    def list_by_agent(self, agent_id: UUID) -> list[Assignment]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(assignments_table).where(assignments_table.c.agent_id == str(agent_id))
            ).mappings().all()
        return [_row_to_assignment(r) for r in rows]

    def list_by_manager(self, manager_id: UUID) -> list[Assignment]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(assignments_table).where(
                    assignments_table.c.manager_id == str(manager_id)
                )
            ).mappings().all()
        return [_row_to_assignment(r) for r in rows]

    def list_active_without_goal_setting(
        self, older_than_days: int, as_of: Optional[date] = None
    ) -> list[Assignment]:
        as_of = as_of or today()
        with self._engine.connect() as conn:
            goal_set_ids = {
                r[0]
                for r in conn.execute(select(goal_settings_table.c.assignment_id))
            }
            rows = conn.execute(
                select(assignments_table).where(
                    assignments_table.c.state == AssignmentState.ACTIVE.value
                )
            ).mappings().all()
        result = []
        for row in rows:
            if row["id"] in goal_set_ids:
                continue
            assignment = _row_to_assignment(row)
            if (as_of - assignment.start_date).days >= older_than_days:
                result.append(assignment)
        return result

    def list_active_older_than(
        self, older_than_days: int, as_of: Optional[date] = None
    ) -> list[Assignment]:
        as_of = as_of or today()
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(assignments_table).where(
                    assignments_table.c.state == AssignmentState.ACTIVE.value
                )
            ).mappings().all()
        return [
            a
            for a in (_row_to_assignment(row) for row in rows)
            if (as_of - a.start_date).days >= older_than_days
        ]

    def add_goal_setting(self, goal_setting: GoalSetting) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(goal_settings_table).values(
                    id=str(goal_setting.id),
                    assignment_id=str(goal_setting.assignment_id),
                    goals=goal_setting.goals,
                    criteria=goal_setting.criteria,
                    set_at=goal_setting.set_at,
                )
            )

    def get_goal_setting(self, assignment_id: UUID) -> Optional[GoalSetting]:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(goal_settings_table).where(
                    goal_settings_table.c.assignment_id == str(assignment_id)
                )
            ).mappings().first()
        if row is None:
            return None
        return GoalSetting(
            id=UUID(row["id"]),
            assignment_id=UUID(row["assignment_id"]),
            goals=row["goals"],
            criteria=list(row["criteria"] or []),
            set_at=row["set_at"],
        )

    def get_closure_record(self, assignment_id: UUID) -> Optional[ClosureRecord]:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(closure_records_table).where(
                    closure_records_table.c.assignment_id == str(assignment_id)
                )
            ).mappings().first()
        if row is None:
            return None
        return ClosureRecord(
            id=UUID(row["id"]),
            assignment_id=UUID(row["assignment_id"]),
            objective_score=row["objective_score"],
            subjective_notes=row["subjective_notes"],
            recorded_at=row["recorded_at"],
        )

    def add_reverse_feedback(self, feedback: ReverseFeedback) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(reverse_feedback_table).values(
                    id=str(feedback.id),
                    assignment_id=str(feedback.assignment_id),
                    notes=feedback.notes,
                    recorded_at=feedback.recorded_at,
                )
            )

    def list_reverse_feedback(self, assignment_id: UUID) -> list[ReverseFeedback]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(reverse_feedback_table).where(
                    reverse_feedback_table.c.assignment_id == str(assignment_id)
                )
            ).mappings().all()
        return [
            ReverseFeedback(
                id=UUID(r["id"]),
                assignment_id=UUID(r["assignment_id"]),
                notes=r["notes"],
                recorded_at=r["recorded_at"],
            )
            for r in rows
        ]


def _assignment_values(
    assignment: Assignment, include_id: bool = True, bump_version: bool = False
) -> dict:
    values = {
        "agent_id": str(assignment.agent_id),
        "manager_id": str(assignment.manager_id),
        "start_date": assignment.start_date,
        "end_date": assignment.end_date,
        "state": assignment.state.value,
        "closed_reason": assignment.closed_reason,
        "closure_note": assignment.closure_note,
        "version": assignment.version + 1 if bump_version else assignment.version,
        "created_at": assignment.created_at,
    }
    if include_id:
        values["id"] = str(assignment.id)
    return values


def _row_to_assignment(row) -> Assignment:
    return Assignment(
        id=UUID(row["id"]),
        agent_id=UUID(row["agent_id"]),
        manager_id=UUID(row["manager_id"]),
        start_date=row["start_date"],
        end_date=row["end_date"],
        state=AssignmentState(row["state"]),
        closed_reason=row["closed_reason"],
        closure_note=row["closure_note"],
        version=row["version"],
        created_at=row["created_at"],
    )
