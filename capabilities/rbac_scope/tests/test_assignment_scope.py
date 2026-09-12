from datetime import date
from uuid import uuid4

import pytest
from assignment.adapters.in_memory import InMemoryAssignmentRepo
from assignment.service import AssignmentService

from rbac_scope import PermissionDenied, Role, ScopedAssignmentQueries, Viewer


@pytest.fixture
def world():
    """A small ITAP world: two managers, two agents, one assignment each,
    plus a third agent with no assignments at all."""
    repo = InMemoryAssignmentRepo()
    service = AssignmentService(repo, min_days_before_closure=30)
    scope = ScopedAssignmentQueries(repo, service)

    manager_a, manager_b = uuid4(), uuid4()
    agent_a, agent_b, agent_c = uuid4(), uuid4(), uuid4()

    assignment_a = service.create_assignment(agent_a, manager_a, date(2026, 1, 1))
    assignment_b = service.create_assignment(agent_b, manager_b, date(2026, 1, 1))

    return {
        "repo": repo,
        "service": service,
        "scope": scope,
        "manager_a": manager_a,
        "manager_b": manager_b,
        "agent_a": agent_a,
        "agent_b": agent_b,
        "agent_c": agent_c,
        "assignment_a": assignment_a,
        "assignment_b": assignment_b,
    }


def test_functional_owner_sees_every_assignment(world):
    owner = Viewer(party_id=uuid4(), role=Role.FUNCTIONAL_OWNER)

    visible = world["scope"].list_visible_assignments(owner)

    assert {a.id for a in visible} == {world["assignment_a"].id, world["assignment_b"].id}


def test_manager_sees_only_their_own_assignments(world):
    manager_view = Viewer(party_id=world["manager_a"], role=Role.MANAGER)

    visible = world["scope"].list_visible_assignments(manager_view)

    assert [a.id for a in visible] == [world["assignment_a"].id]


def test_agent_sees_only_their_own_assignments(world):
    agent_view = Viewer(party_id=world["agent_b"], role=Role.AGENT)

    visible = world["scope"].list_visible_assignments(agent_view)

    assert [a.id for a in visible] == [world["assignment_b"].id]


def test_agent_cannot_fetch_another_agents_assignment(world):
    agent_view = Viewer(party_id=world["agent_a"], role=Role.AGENT)

    with pytest.raises(PermissionDenied):
        world["scope"].get_assignment(agent_view, world["assignment_b"].id)


def test_manager_cannot_fetch_an_assignment_not_theirs(world):
    manager_view = Viewer(party_id=world["manager_a"], role=Role.MANAGER)

    with pytest.raises(PermissionDenied):
        world["scope"].get_assignment(manager_view, world["assignment_b"].id)


def test_agent_can_see_their_own_closure_record(world):
    world["service"].close_assignment(
        world["assignment_a"].id,
        objective_score=4.0,
        subjective_notes="Great quarter",
        as_of=date(2026, 3, 1),
    )
    agent_view = Viewer(party_id=world["agent_a"], role=Role.AGENT)

    record = world["scope"].get_closure_record(agent_view, world["assignment_a"].id)

    assert record.objective_score == 4.0


def test_agent_cannot_see_another_agents_closure_record(world):
    world["service"].close_assignment(
        world["assignment_a"].id,
        objective_score=4.0,
        subjective_notes="Great quarter",
        as_of=date(2026, 3, 1),
    )
    other_agent_view = Viewer(party_id=world["agent_b"], role=Role.AGENT)

    with pytest.raises(PermissionDenied):
        world["scope"].get_closure_record(other_agent_view, world["assignment_a"].id)


def test_reverse_feedback_inherits_assignment_visibility(world):
    world["service"].record_reverse_feedback(world["assignment_a"].id, "Great mentor")
    manager_view = Viewer(party_id=world["manager_a"], role=Role.MANAGER)
    other_manager_view = Viewer(party_id=world["manager_b"], role=Role.MANAGER)

    feedback = world["scope"].list_reverse_feedback(manager_view, world["assignment_a"].id)
    assert [f.notes for f in feedback] == ["Great mentor"]

    with pytest.raises(PermissionDenied):
        world["scope"].list_reverse_feedback(other_manager_view, world["assignment_a"].id)


def test_overdue_goal_setting_scoped_by_role(world):
    owner_view = Viewer(party_id=uuid4(), role=Role.FUNCTIONAL_OWNER)
    manager_a_view = Viewer(party_id=world["manager_a"], role=Role.MANAGER)
    agent_view = Viewer(party_id=world["agent_a"], role=Role.AGENT)

    owner_overdue = world["scope"].list_overdue_goal_setting(
        owner_view, older_than_days=14, as_of=date(2026, 2, 1)
    )
    manager_overdue = world["scope"].list_overdue_goal_setting(
        manager_a_view, older_than_days=14, as_of=date(2026, 2, 1)
    )

    assert {a.id for a in owner_overdue} == {world["assignment_a"].id, world["assignment_b"].id}
    assert [a.id for a in manager_overdue] == [world["assignment_a"].id]

    with pytest.raises(PermissionDenied):
        world["scope"].list_overdue_goal_setting(agent_view, older_than_days=14)


def test_consolidated_score_functional_owner_and_self_only(world):
    world["service"].close_assignment(
        world["assignment_a"].id,
        objective_score=4.0,
        subjective_notes="Great quarter",
        as_of=date(2026, 3, 1),
    )
    owner_view = Viewer(party_id=uuid4(), role=Role.FUNCTIONAL_OWNER)
    self_view = Viewer(party_id=world["agent_a"], role=Role.AGENT)
    other_agent_view = Viewer(party_id=world["agent_b"], role=Role.AGENT)
    manager_view = Viewer(party_id=world["manager_a"], role=Role.MANAGER)

    assert world["scope"].consolidated_score(owner_view, world["agent_a"]) == 4.0
    assert world["scope"].consolidated_score(self_view, world["agent_a"]) == 4.0

    with pytest.raises(PermissionDenied):
        world["scope"].consolidated_score(other_agent_view, world["agent_a"])

    with pytest.raises(PermissionDenied):
        world["scope"].consolidated_score(manager_view, world["agent_a"])


def test_consolidated_score_none_when_no_closures_yet(world):
    owner_view = Viewer(party_id=uuid4(), role=Role.FUNCTIONAL_OWNER)

    assert world["scope"].consolidated_score(owner_view, world["agent_c"]) is None
