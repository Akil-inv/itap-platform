from party_identity.domain import Party


def test_with_attributes_returns_new_immutable_instance():
    original = Party(party_type="agent", display_name="Jane Doe", attributes={"a": 1})

    updated = original.with_attributes(b=2)

    assert original.attributes == {"a": 1}
    assert updated.attributes == {"a": 1, "b": 2}
    assert updated.id == original.id
