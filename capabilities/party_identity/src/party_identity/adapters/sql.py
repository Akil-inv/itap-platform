"""SQL adapter for PartyRepo, built on SQLAlchemy Core only (no ORM, no
Postgres-only features) so the same code runs against Postgres today and
against another SQL engine later without changes — per the project's
Postgres-to-Impala/Iceberg migration constraint documented in
docs/architecture.md.

Deliberately avoids:
  - autoincrement / SERIAL primary keys (ids are app-generated UUIDs)
  - foreign key constraints as a correctness dependency
  - multi-table transactions spanning other capability blocks
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Engine,
    MetaData,
    String,
    Table,
    insert,
    select,
    update,
)

from ..domain import Party, PartyNotFound

metadata = MetaData()

parties_table = Table(
    "parties",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("party_type", String(255), nullable=False, index=True),
    Column("display_name", String(255), nullable=False),
    Column("attributes", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def create_schema(engine: Engine) -> None:
    """Create the parties table if it does not exist. Call once at app
    startup; not invoked implicitly by the adapter."""
    metadata.create_all(engine, tables=[parties_table])


class SqlPartyRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, party: Party) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(parties_table).values(
                    id=str(party.id),
                    party_type=party.party_type,
                    display_name=party.display_name,
                    attributes=party.attributes,
                    created_at=party.created_at,
                )
            )

    def get(self, party_id: UUID) -> Party:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(parties_table).where(parties_table.c.id == str(party_id))
            ).mappings().first()
        if row is None:
            raise PartyNotFound(party_id)
        return _row_to_party(row)

    def list_by_type(self, party_type: str) -> list[Party]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(parties_table).where(parties_table.c.party_type == party_type)
            ).mappings().all()
        return [_row_to_party(row) for row in rows]

    def update_attributes(self, party_id: UUID, **updates: object) -> Party:
        current = self.get(party_id)
        updated = current.with_attributes(**updates)
        with self._engine.begin() as conn:
            result = conn.execute(
                update(parties_table)
                .where(parties_table.c.id == str(party_id))
                .values(attributes=updated.attributes)
            )
            if result.rowcount == 0:
                raise PartyNotFound(party_id)
        return updated


def _row_to_party(row) -> Party:
    return Party(
        id=UUID(row["id"]),
        party_type=row["party_type"],
        display_name=row["display_name"],
        attributes=dict(row["attributes"] or {}),
        created_at=row["created_at"],
    )
