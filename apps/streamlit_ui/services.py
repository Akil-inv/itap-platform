"""Wires the capability packages together for the Streamlit app. This is
the only file in apps/ that is allowed to import adapters directly — every
view module talks to the services/repos handed to it, never to SQLAlchemy
or a concrete adapter itself.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import streamlit as st
from sqlalchemy import Engine, create_engine

from assignment.adapters.sql import SqlAssignmentRepo
from assignment.adapters.sql import create_schema as create_assignment_schema
from assignment.ports import AssignmentRepo
from assignment.service import AssignmentService
from party_identity.adapters.sql import SqlPartyRepo
from party_identity.adapters.sql import create_schema as create_party_schema
from party_identity.ports import PartyRepo
from rbac_scope import ScopedAssignmentQueries
from rotation_plan.adapters.sql import SqlRotationPlanRepo
from rotation_plan.adapters.sql import create_schema as create_rotation_plan_schema
from rotation_plan.ports import RotationPlanRepo
from rotation_plan.service import RotationPlanService


@dataclass
class Services:
    engine: Engine
    party_repo: PartyRepo
    assignment_repo: AssignmentRepo
    assignment_service: AssignmentService
    scope: ScopedAssignmentQueries
    rotation_plan_repo: RotationPlanRepo
    rotation_plan_service: RotationPlanService


@st.cache_resource
def get_services() -> Services:
    database_url = os.environ.get("DATABASE_URL", "sqlite:///itap.db")
    min_days = int(os.environ.get("MIN_DAYS_BEFORE_CLOSURE", "30"))

    engine = create_engine(database_url)
    create_party_schema(engine)
    create_assignment_schema(engine)
    create_rotation_plan_schema(engine)

    party_repo = SqlPartyRepo(engine)
    assignment_repo = SqlAssignmentRepo(engine)
    assignment_service = AssignmentService(assignment_repo, min_days_before_closure=min_days)
    scope = ScopedAssignmentQueries(assignment_repo, assignment_service)
    rotation_plan_repo = SqlRotationPlanRepo(engine)
    rotation_plan_service = RotationPlanService(rotation_plan_repo)

    return Services(
        engine=engine,
        party_repo=party_repo,
        assignment_repo=assignment_repo,
        assignment_service=assignment_service,
        scope=scope,
        rotation_plan_repo=rotation_plan_repo,
        rotation_plan_service=rotation_plan_service,
    )
