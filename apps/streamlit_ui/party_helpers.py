from __future__ import annotations

from collections import Counter
from uuid import UUID

from party_identity.domain import Party
from party_identity.ports import PartyRepo


def party_label(party: Party) -> str:
    return f"{party.display_name} ({party.party_type})"


def disambiguate_labels(parties: list[Party], label_fn=party_label) -> dict[str, Party]:
    """Maps a display label to each Party, appending a short id suffix
    only to names that collide within this specific list — two Agents
    both named "Casey" are otherwise visually indistinguishable in every
    dropdown, sign-in button, and selection form. `label_fn` picks the
    base label (defaults to "name (type)"; pass `lambda p: p.display_name`
    for contexts — like the sign-in page — where the type is already
    shown as a section heading and would be redundant)."""
    name_counts = Counter(p.display_name for p in parties)
    labels: dict[str, Party] = {}
    for party in parties:
        base = label_fn(party)
        if name_counts[party.display_name] > 1:
            base = f"{base} · {str(party.id)[:8]}"
        labels[base] = party
    return labels


def safe_get_name(party_repo: PartyRepo, party_id: UUID) -> str:
    try:
        return party_repo.get(party_id).display_name
    except Exception:
        return f"<unknown {party_id}>"
