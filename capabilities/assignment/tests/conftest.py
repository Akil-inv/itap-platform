import pytest
from sqlalchemy import create_engine

from assignment.adapters.in_memory import InMemoryAssignmentRepo
from assignment.adapters.sql import SqlAssignmentRepo, create_schema


@pytest.fixture(params=["in_memory", "sql_sqlite"])
def assignment_repo(request):
    """Runs every test in this suite against each adapter."""
    if request.param == "in_memory":
        return InMemoryAssignmentRepo()

    engine = create_engine("sqlite:///:memory:")
    create_schema(engine)
    return SqlAssignmentRepo(engine)
