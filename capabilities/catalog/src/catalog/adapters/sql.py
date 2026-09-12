"""SQL adapter, SQLAlchemy Core only — same conventions as
capabilities/assignment/adapters/sql.py and
capabilities/rotation_plan/adapters/sql.py: app-generated UUID keys, no
FK-constraint reliance, no autoincrement, additive-only self-healing
column migration via `_ensure_columns`.

`AssociateProfile.experience`/`project_highlights` are lists of small
dataclasses (ExperienceEntry/ProjectHighlight) — stored as plain JSON
(list of dicts), same "JSON can't hold a dataclass or a date directly"
handling as rotation_plan's stage maps: dates are encoded as ISO strings
and decoded back on the way out.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Engine,
    MetaData,
    String,
    Table,
    Text,
    inspect,
    insert,
    select,
    text,
    update,
)

from ..domain import (
    AnnualLeave,
    AssociateProfile,
    AssociateSkill,
    CcaActivity,
    CcaActivityNotFound,
    CcaStatus,
    ExperienceEntry,
    InterestActivity,
    InterestFlag,
    InterestTargetType,
    ProjectHighlight,
    Skill,
    SkillNotFound,
    SkillSource,
    Team,
    TeamNotFound,
)

metadata = MetaData()

skills_table = Table(
    "catalog_skills",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

teams_table = Table(
    "catalog_teams",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("manager_id", String(36), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

cca_activities_table = Table(
    "catalog_cca_activities",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("organizer_manager_id", String(36), nullable=False, index=True),
    Column("status", String(16), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

associate_skills_table = Table(
    "catalog_associate_skills",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("agent_id", String(36), nullable=False, index=True),
    Column("skill_id", String(36), nullable=False, index=True),
    Column("source", String(16), nullable=False),
    Column("source_detail", Text, nullable=False),
    Column("added_at", DateTime(timezone=True), nullable=False),
)

associate_profiles_table = Table(
    "catalog_associate_profiles",
    metadata,
    Column("agent_id", String(36), primary_key=True),
    Column("bio", Text, nullable=False),
    Column("photo_url", String(2048), nullable=True),
    Column("experience", JSON, nullable=False),
    Column("project_highlights", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

interest_flags_table = Table(
    "catalog_interest_flags",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("agent_id", String(36), nullable=False, index=True),
    Column("target_type", String(16), nullable=False),
    Column("target_id", String(36), nullable=False),
    Column("active", Boolean, nullable=False),
    Column("flagged_at", DateTime(timezone=True), nullable=False),
)

interest_activity_table = Table(
    "catalog_interest_activity",
    metadata,
    Column("agent_id", String(36), primary_key=True),
    Column("raised_at", DateTime(timezone=True), nullable=True),
    Column("seen_at", DateTime(timezone=True), nullable=True),
)

annual_leave_table = Table(
    "catalog_annual_leave",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("agent_id", String(36), nullable=False, index=True),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=False),
    Column("note", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

_ALL_TABLES = [
    skills_table,
    teams_table,
    cca_activities_table,
    associate_skills_table,
    associate_profiles_table,
    interest_flags_table,
    interest_activity_table,
    annual_leave_table,
]


def _ensure_columns(engine: Engine, table: Table, backfill: Optional[dict] = None) -> None:
    """Additive-only schema patch — see capabilities/assignment/adapters/
    sql.py for the full rationale. Not a real migration framework."""
    inspector = inspect(engine)
    if table.name not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns(table.name)}
    missing = [column for column in table.columns if column.name not in existing]
    if not missing:
        return
    backfill = backfill or {}
    with engine.begin() as conn:
        for column in missing:
            col_type = column.type.compile(dialect=engine.dialect)
            conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"))
            if column.name in backfill:
                conn.execute(update(table).values(**{column.name: backfill[column.name]}))


def create_schema(engine: Engine) -> None:
    metadata.create_all(engine, tables=_ALL_TABLES)


class SqlCatalogRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # -- Skills --
    def add_skill(self, skill: Skill) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(skills_table).values(
                    id=str(skill.id), name=skill.name, created_at=skill.created_at
                )
            )

    def get_skill(self, skill_id: UUID) -> Skill:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(skills_table).where(skills_table.c.id == str(skill_id))
            ).mappings().first()
        if row is None:
            raise SkillNotFound(skill_id)
        return Skill(id=UUID(row["id"]), name=row["name"], created_at=row["created_at"])

    def list_skills(self) -> list[Skill]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(skills_table)).mappings().all()
        return [Skill(id=UUID(r["id"]), name=r["name"], created_at=r["created_at"]) for r in rows]

    # -- Teams --
    def add_team(self, team: Team) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(teams_table).values(
                    id=str(team.id),
                    name=team.name,
                    manager_id=str(team.manager_id),
                    created_at=team.created_at,
                )
            )

    def get_team(self, team_id: UUID) -> Team:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(teams_table).where(teams_table.c.id == str(team_id))
            ).mappings().first()
        if row is None:
            raise TeamNotFound(team_id)
        return _row_to_team(row)

    def list_teams(self) -> list[Team]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(teams_table)).mappings().all()
        return [_row_to_team(r) for r in rows]

    # -- CCA activities --
    def add_cca_activity(self, cca: CcaActivity) -> None:
        with self._engine.begin() as conn:
            conn.execute(insert(cca_activities_table).values(**_cca_values(cca)))

    def get_cca_activity(self, cca_id: UUID) -> CcaActivity:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(cca_activities_table).where(cca_activities_table.c.id == str(cca_id))
            ).mappings().first()
        if row is None:
            raise CcaActivityNotFound(cca_id)
        return _row_to_cca(row)

    def list_cca_activities(self) -> list[CcaActivity]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(cca_activities_table)).mappings().all()
        return [_row_to_cca(r) for r in rows]

    def update_cca_activity(self, cca: CcaActivity) -> None:
        with self._engine.begin() as conn:
            result = conn.execute(
                update(cca_activities_table)
                .where(cca_activities_table.c.id == str(cca.id))
                .values(**_cca_values(cca, include_id=False))
            )
            if result.rowcount == 0:
                raise CcaActivityNotFound(cca.id)

    # -- Associate-declared skills --
    def add_associate_skill(self, associate_skill: AssociateSkill) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(associate_skills_table).values(
                    id=str(associate_skill.id),
                    agent_id=str(associate_skill.agent_id),
                    skill_id=str(associate_skill.skill_id),
                    source=associate_skill.source.value,
                    source_detail=associate_skill.source_detail,
                    added_at=associate_skill.added_at,
                )
            )

    def list_associate_skills(self, agent_id: UUID) -> list[AssociateSkill]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(associate_skills_table).where(
                    associate_skills_table.c.agent_id == str(agent_id)
                )
            ).mappings().all()
        return [
            AssociateSkill(
                id=UUID(r["id"]),
                agent_id=UUID(r["agent_id"]),
                skill_id=UUID(r["skill_id"]),
                source=SkillSource(r["source"]),
                source_detail=r["source_detail"],
                added_at=r["added_at"],
            )
            for r in rows
        ]

    # -- Associate profile --
    def get_profile(self, agent_id: UUID) -> Optional[AssociateProfile]:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(associate_profiles_table).where(
                    associate_profiles_table.c.agent_id == str(agent_id)
                )
            ).mappings().first()
        return None if row is None else _row_to_profile(row)

    def upsert_profile(self, profile: AssociateProfile) -> None:
        values = _profile_values(profile)
        with self._engine.begin() as conn:
            result = conn.execute(
                update(associate_profiles_table)
                .where(associate_profiles_table.c.agent_id == str(profile.agent_id))
                .values(**{k: v for k, v in values.items() if k != "agent_id"})
            )
            if result.rowcount == 0:
                conn.execute(insert(associate_profiles_table).values(**values))

    # -- Interest signaling --
    def add_interest_flag(self, flag: InterestFlag) -> None:
        with self._engine.begin() as conn:
            conn.execute(insert(interest_flags_table).values(**_flag_values(flag)))

    def update_interest_flag(self, flag: InterestFlag) -> None:
        with self._engine.begin() as conn:
            result = conn.execute(
                update(interest_flags_table)
                .where(interest_flags_table.c.id == str(flag.id))
                .values(**{k: v for k, v in _flag_values(flag).items() if k != "id"})
            )
            if result.rowcount == 0:
                raise ValueError(f"InterestFlag {flag.id} not found")

    def list_interest_flags(self, agent_id: UUID) -> list[InterestFlag]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(interest_flags_table).where(
                    interest_flags_table.c.agent_id == str(agent_id)
                )
            ).mappings().all()
        return [_row_to_flag(r) for r in rows]

    def get_interest_activity(self, agent_id: UUID) -> Optional[InterestActivity]:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(interest_activity_table).where(
                    interest_activity_table.c.agent_id == str(agent_id)
                )
            ).mappings().first()
        if row is None:
            return None
        return InterestActivity(
            agent_id=UUID(row["agent_id"]), raised_at=row["raised_at"], seen_at=row["seen_at"]
        )

    def upsert_interest_activity(self, activity: InterestActivity) -> None:
        values = {
            "agent_id": str(activity.agent_id),
            "raised_at": activity.raised_at,
            "seen_at": activity.seen_at,
        }
        with self._engine.begin() as conn:
            result = conn.execute(
                update(interest_activity_table)
                .where(interest_activity_table.c.agent_id == str(activity.agent_id))
                .values(raised_at=values["raised_at"], seen_at=values["seen_at"])
            )
            if result.rowcount == 0:
                conn.execute(insert(interest_activity_table).values(**values))

    # -- Annual leave --
    def add_leave(self, leave: AnnualLeave) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(annual_leave_table).values(
                    id=str(leave.id),
                    agent_id=str(leave.agent_id),
                    start_date=leave.start_date,
                    end_date=leave.end_date,
                    note=leave.note,
                    created_at=leave.created_at,
                )
            )

    def list_leave(self, agent_id: UUID) -> list[AnnualLeave]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(annual_leave_table).where(
                    annual_leave_table.c.agent_id == str(agent_id)
                )
            ).mappings().all()
        return [
            AnnualLeave(
                id=UUID(r["id"]),
                agent_id=UUID(r["agent_id"]),
                start_date=r["start_date"],
                end_date=r["end_date"],
                note=r["note"],
                created_at=r["created_at"],
            )
            for r in rows
        ]


def _row_to_team(row) -> Team:
    return Team(
        id=UUID(row["id"]),
        name=row["name"],
        manager_id=UUID(row["manager_id"]),
        created_at=row["created_at"],
    )


def _cca_values(cca: CcaActivity, include_id: bool = True) -> dict:
    values = {
        "name": cca.name,
        "organizer_manager_id": str(cca.organizer_manager_id),
        "status": cca.status.value,
        "created_at": cca.created_at,
    }
    if include_id:
        values["id"] = str(cca.id)
    return values


def _row_to_cca(row) -> CcaActivity:
    return CcaActivity(
        id=UUID(row["id"]),
        name=row["name"],
        organizer_manager_id=UUID(row["organizer_manager_id"]),
        status=CcaStatus(row["status"]),
        created_at=row["created_at"],
    )


def _entry_to_dict(entry: ExperienceEntry) -> dict:
    return {
        "title": entry.title,
        "description": entry.description,
        "start_date": entry.start_date.isoformat() if entry.start_date else None,
        "end_date": entry.end_date.isoformat() if entry.end_date else None,
    }


def _dict_to_entry(d: dict) -> ExperienceEntry:
    return ExperienceEntry(
        title=d["title"],
        description=d.get("description", ""),
        start_date=date.fromisoformat(d["start_date"]) if d.get("start_date") else None,
        end_date=date.fromisoformat(d["end_date"]) if d.get("end_date") else None,
    )


def _highlight_to_dict(h: ProjectHighlight) -> dict:
    return {"title": h.title, "description": h.description}


def _dict_to_highlight(d: dict) -> ProjectHighlight:
    return ProjectHighlight(title=d["title"], description=d.get("description", ""))


def _profile_values(profile: AssociateProfile) -> dict:
    return {
        "agent_id": str(profile.agent_id),
        "bio": profile.bio,
        "photo_url": profile.photo_url,
        "experience": [_entry_to_dict(e) for e in profile.experience],
        "project_highlights": [_highlight_to_dict(h) for h in profile.project_highlights],
        "updated_at": profile.updated_at,
    }


def _row_to_profile(row) -> AssociateProfile:
    return AssociateProfile(
        agent_id=UUID(row["agent_id"]),
        bio=row["bio"],
        photo_url=row["photo_url"],
        experience=[_dict_to_entry(e) for e in (row["experience"] or [])],
        project_highlights=[_dict_to_highlight(h) for h in (row["project_highlights"] or [])],
        updated_at=row["updated_at"],
    )


def _flag_values(flag: InterestFlag) -> dict:
    return {
        "id": str(flag.id),
        "agent_id": str(flag.agent_id),
        "target_type": flag.target_type.value,
        "target_id": str(flag.target_id),
        "active": flag.active,
        "flagged_at": flag.flagged_at,
    }


def _row_to_flag(row) -> InterestFlag:
    return InterestFlag(
        id=UUID(row["id"]),
        agent_id=UUID(row["agent_id"]),
        target_type=InterestTargetType(row["target_type"]),
        target_id=UUID(row["target_id"]),
        active=row["active"],
        flagged_at=row["flagged_at"],
    )
