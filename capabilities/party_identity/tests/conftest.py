import pytest
from sqlalchemy import create_engine

from party_identity.adapters.in_memory import InMemoryPartyRepo
from party_identity.adapters.sql import SqlPartyRepo, create_schema


@pytest.fixture(params=["in_memory", "sql_sqlite"])
def party_repo(request):
    """Runs every test in this suite against each adapter, proving both
    satisfy the same PartyRepo contract."""
    if request.param == "in_memory":
        return InMemoryPartyRepo()

    engine = create_engine("sqlite:///:memory:")
    create_schema(engine)
    return SqlPartyRepo(engine)
