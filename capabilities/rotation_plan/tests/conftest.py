import pytest
from sqlalchemy import create_engine

from rotation_plan.adapters.in_memory import InMemoryRotationPlanRepo
from rotation_plan.adapters.sql import SqlRotationPlanRepo, create_schema


@pytest.fixture(params=["in_memory", "sql_sqlite"])
def rotation_plan_repo(request):
    """Runs every test in this suite against each adapter."""
    if request.param == "in_memory":
        return InMemoryRotationPlanRepo()

    engine = create_engine("sqlite:///:memory:")
    create_schema(engine)
    return SqlRotationPlanRepo(engine)
