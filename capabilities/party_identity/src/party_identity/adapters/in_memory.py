"""Reference adapter — used in tests and for local/offline development of
any block that depends on PartyRepo, without needing a database."""
from __future__ import annotations

from uuid import UUID

from ..domain import Party, PartyNotFound


class InMemoryPartyRepo:
    def __init__(self) -> None:
        self._parties: dict[UUID, Party] = {}

    def add(self, party: Party) -> None:
        if party.id in self._parties:
            raise ValueError(f"Party {party.id} already exists")
        self._parties[party.id] = party

    def get(self, party_id: UUID) -> Party:
        try:
            return self._parties[party_id]
        except KeyError:
            raise PartyNotFound(party_id) from None

    def list_by_type(self, party_type: str) -> list[Party]:
        return [p for p in self._parties.values() if p.party_type == party_type]

    def update_attributes(self, party_id: UUID, **updates: object) -> Party:
        current = self.get(party_id)
        updated = current.with_attributes(**updates)
        self._parties[party_id] = updated
        return updated
