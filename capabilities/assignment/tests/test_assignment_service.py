from datetime import date
from uuid import uuid4

import pytest

from assignment.adapters.in_memory import InMemoryAssignmentRepo
from assignment.domain import AssignmentState
from assignment.rules import TransitionDenied
from assignment.service import AssignmentService


@pytest.fixture
def service():
    return AssignmentService(InMemoryAssignmentRepo(), min_days_before_closure=30)


def test_create_assignment_starts_active_without_goal_setting(service):
    agent_id, manager_id = uuid4(), uuid4()

    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    assert assignment.state == AssignmentState.ACTIVE  # not gated by goal setting


def test_extension_requires_the_assignments_own_manager(service):
    agent_id, manager_id, other_manager = uuid4(), uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    with pytest.raises(TransitionDenied):
        service.request_extension(assignment.id, requested_by=other_manager, new_end_date=date(2026, 12, 31))

    updated = service.request_extension(
        assignment.id, requested_by=manager_id, new_end_date=date(2026, 12, 31)
    )
    assert updated.end_date == date(2026, 12, 31)
    assert updated.state == AssignmentState.ACTIVE


def test_closure_denied_before_minimum_elapsed_period(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    with pytest.raises(TransitionDenied, match="30 days"):
        service.close_assignment(
            assignment.id,
            objective_score=4.0,
            subjective_notes="Too early",
            as_of=date(2026, 1, 10),
        )


def test_closure_allowed_after_minimum_elapsed_period(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    closed = service.close_assignment(
        assignment.id,
        objective_score=4.5,
        subjective_notes="Strong quarter",
        as_of=date(2026, 3, 1),
    )

    assert closed.state == AssignmentState.CLOSED
    assert closed.closed_reason == "completed"


def test_cannot_close_an_already_closed_assignment(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))
    service.close_assignment(
        assignment.id, objective_score=4.0, subjective_notes="Done", as_of=date(2026, 3, 1)
    )

    with pytest.raises(TransitionDenied):
        service.close_assignment(
            assignment.id, objective_score=4.0, subjective_notes="Again?", as_of=date(2026, 4, 1)
        )


def test_swap_to_new_manager_closes_old_and_opens_new(service):
    agent_id, manager_id, new_manager_id = uuid4(), uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    new_assignment = service.swap_to_new_manager(
        assignment.id,
        new_manager_id=new_manager_id,
        objective_score=4.2,
        subjective_notes="Ready for the next rotation",
        new_start_date=date(2026, 4, 1),
        as_of=date(2026, 3, 1),
    )

    old = service._repo.get(assignment.id)
    assert old.state == AssignmentState.CLOSED
    assert old.closed_reason == "swapped"
    assert new_assignment.manager_id == new_manager_id
    assert new_assignment.agent_id == agent_id
    assert new_assignment.state == AssignmentState.ACTIVE


def test_cross_team_bifurcation_each_assignment_independent(service):
    agent_id = uuid4()
    manager_a, manager_b = uuid4(), uuid4()
    assignment_a = service.create_assignment(agent_id, manager_a, date(2026, 1, 1))
    assignment_b = service.create_assignment(agent_id, manager_b, date(2026, 1, 1))

    # manager_b closing their assignment must not affect manager_a's
    service.close_assignment(
        assignment_b.id, objective_score=3.5, subjective_notes="Fine", as_of=date(2026, 3, 1)
    )

    assert service._repo.get(assignment_a.id).state == AssignmentState.ACTIVE
    assert service._repo.get(assignment_b.id).state == AssignmentState.CLOSED


def test_reverse_feedback_allowed_independent_of_assignment_state(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    feedback = service.record_reverse_feedback(assignment.id, "Great mentor, very supportive")

    assert feedback.assignment_id == assignment.id


def test_list_overdue_goal_setting_reflects_reminder_need(service):
    agent_id, manager_id = uuid4(), uuid4()
    overdue = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))
    on_time = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))
    service.record_goal_setting(on_time.id, "Ship feature X")

    overdue_list = service.list_overdue_goal_setting(older_than_days=14, as_of=date(2026, 2, 1))

    assert [a.id for a in overdue_list] == [overdue.id]
