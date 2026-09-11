import pytest

from party_identity.domain import Party, PartyNotFound


def test_add_and_get_round_trips(party_repo):
    party = Party(party_type="agent", display_name="Jane Doe")
    party_repo.add(party)

    fetched = party_repo.get(party.id)

    assert fetched.id == party.id
    assert fetched.party_type == "agent"
    assert fetched.display_name == "Jane Doe"


def test_get_missing_raises(party_repo):
    from uuid import uuid4

    with pytest.raises(PartyNotFound):
        party_repo.get(uuid4())


def test_add_duplicate_id_raises(party_repo):
    party = Party(party_type="agent", display_name="Jane Doe")
    party_repo.add(party)

    with pytest.raises(Exception):
        party_repo.add(party)


def test_list_by_type_filters_correctly(party_repo):
    agent = Party(party_type="agent", display_name="Jane Doe")
    manager = Party(party_type="manager", display_name="John Smith")
    party_repo.add(agent)
    party_repo.add(manager)

    agents = party_repo.list_by_type("agent")

    assert [p.id for p in agents] == [agent.id]


def test_update_attributes_merges_and_persists(party_repo):
    party = Party(
        party_type="agent",
        display_name="Jane Doe",
        attributes={"cohort": "2026-Q3"},
    )
    party_repo.add(party)

    updated = party_repo.update_attributes(party.id, region="APAC")

    assert updated.attributes == {"cohort": "2026-Q3", "region": "APAC"}
    assert party_repo.get(party.id).attributes == {
        "cohort": "2026-Q3",
        "region": "APAC",
    }


def test_update_attributes_missing_raises(party_repo):
    from uuid import uuid4

    with pytest.raises(PartyNotFound):
        party_repo.update_attributes(uuid4(), region="APAC")
