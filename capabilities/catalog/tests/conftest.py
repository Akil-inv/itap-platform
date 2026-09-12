import pytest
from sqlalchemy import create_engine

from catalog.adapters.in_memory import InMemoryCatalogRepo
from catalog.adapters.sql import SqlCatalogRepo, create_schema


@pytest.fixture(params=["in_memory", "sql_sqlite"])
def catalog_repo(request):
    """Runs every test in this suite against each adapter."""
    if request.param == "in_memory":
        return InMemoryCatalogRepo()

    engine = create_engine("sqlite:///:memory:")
    create_schema(engine)
    return SqlCatalogRepo(engine)
