"""Capability block 1: Party/Identity — domain model.

A Party is any addressable actor in a system built on this catalog: a
person, a team, a role-holder. This module must never import or reference
a domain-specific noun (e.g. "Intern", "Manager", "Technician") — those are
supplied by the consuming application as plain strings/config, not as code
here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Party:
    """An addressable actor.

    `party_type` and `attributes` are where domain vocabulary lives —
    this class itself carries no opinion about what a "type" means.
    """

    party_type: str
    display_name: str
    id: UUID = field(default_factory=uuid4)
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def with_attributes(self, **updates: Any) -> "Party":
        merged = {**self.attributes, **updates}
        return Party(
            party_type=self.party_type,
            display_name=self.display_name,
            id=self.id,
            attributes=merged,
            created_at=self.created_at,
        )


class PartyNotFound(Exception):
    def __init__(self, party_id: UUID):
        super().__init__(f"Party {party_id} not found")
        self.party_id = party_id
