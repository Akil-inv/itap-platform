"""Port for block 1. Any adapter (in-memory, Postgres, ...) must satisfy this
Protocol. Nothing outside this module's adapters may import a concrete
adapter directly — callers depend on PartyRepo only.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .domain import Party


class PartyRepo(Protocol):
    def add(self, party: Party) -> None:
        """Persist a new Party. Raises if the id already exists."""
        ...

    def get(self, party_id: UUID) -> Party:
        """Fetch a Party by id. Raises PartyNotFound if missing."""
        ...

    def list_by_type(self, party_type: str) -> list[Party]:
        """List all Parties of a given type."""
        ...

    def update_attributes(self, party_id: UUID, **updates: object) -> Party:
        """Merge `updates` into the Party's attributes and persist. Returns
        the updated Party. Raises PartyNotFound if missing."""
        ...
