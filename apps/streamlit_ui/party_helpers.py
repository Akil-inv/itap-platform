from __future__ import annotations

from uuid import UUID

from party_identity.domain import Party
from party_identity.ports import PartyRepo


def party_label(party: Party) -> str:
    return f"{party.display_name} ({party.party_type})"


def safe_get_name(party_repo: PartyRepo, party_id: UUID) -> str:
    try:
        return party_repo.get(party_id).display_name
    except Exception:
        return f"<unknown {party_id}>"
