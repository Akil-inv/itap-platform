from datetime import date
from uuid import uuid4

import pytest

from assignment.adapters.in_memory import InMemoryAssignmentRepo
from assignment.domain import (
    AssignmentState,
    ClosureRecord,
    ConcurrentModification,
    DuplicateAssignment,
)
from assignment.rules import TransitionDenied
from assignment.service import AssignmentService


@pytest.fixture
def service():
    return AssignmentService(InMemoryAssignmentRepo(), min_days_before_closure=30)


def _close(service, assignment_id, as_of=date(2026, 3, 1), score=4.0, notes="Solid quarter"):
    """Most closure tests don't care about the goal-setting requirement
    itself — set it first so the test's actual point isn't obscured."""
    service.record_goal_setting(assignment_id, "Ship feature X")
    return service.close_assignment(
        assignment_id, objective_score=score, subjective_notes=notes, as_of=as_of
    )


def test_create_assignment_starts_active_without_goal_setting(service):
    agent_id, manager_id = uuid4(), uuid4()

    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    assert assignment.state == AssignmentState.ACTIVE  # not gated by goal setting


def test_create_assignment_rejects_end_before_start(service):
    agent_id, manager_id = uuid4(), uuid4()

    with pytest.raises(ValueError):
        service.create_assignment(
            agent_id, manager_id, date(2026, 6, 1), end_date=date(2026, 1, 1)
        )


def test_create_assignment_rejects_duplicate_active_pair(service):
    agent_id, manager_id = uuid4(), uuid4()
    service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    with pytest.raises(DuplicateAssignment):
        service.create_assignment(agent_id, manager_id, date(2026, 2, 1))


def test_create_assignment_allows_same_pair_once_first_is_closed(service):
    agent_id, manager_id = uuid4(), uuid4()
    first = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))
    _close(service, first.id)

    # closed, so a new one with the same pair is a legitimate re-engagement
    second = service.create_assignment(agent_id, manager_id, date(2026, 4, 1))
    assert second.state == AssignmentState.ACTIVE


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


def test_extension_cannot_shorten_the_assignment(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(
        agent_id, manager_id, date(2026, 1, 1), end_date=date(2026, 6, 1)
    )

    with pytest.raises(TransitionDenied, match="later than"):
        service.request_extension(
            assignment.id, requested_by=manager_id, new_end_date=date(2026, 3, 1)
        )


def test_extension_rejects_same_date_as_current_end(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(
        agent_id, manager_id, date(2026, 1, 1), end_date=date(2026, 6, 1)
    )

    with pytest.raises(TransitionDenied):
        service.request_extension(
            assignment.id, requested_by=manager_id, new_end_date=date(2026, 6, 1)
        )


def test_closure_denied_before_minimum_elapsed_period(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))
    service.record_goal_setting(assignment.id, "Ship feature X")

    with pytest.raises(TransitionDenied, match="30 days"):
        service.close_assignment(
            assignment.id,
            objective_score=4.0,
            subjective_notes="Too early",
            as_of=date(2026, 1, 10),
        )


def test_closure_denied_without_goal_setting(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    with pytest.raises(TransitionDenied, match="goal setting"):
        service.close_assignment(
            assignment.id,
            objective_score=4.0,
            subjective_notes="No goals were ever set",
            as_of=date(2026, 3, 1),
        )


def test_closure_rejects_out_of_range_score(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))
    service.record_goal_setting(assignment.id, "Ship feature X")

    with pytest.raises(ValueError):
        service.close_assignment(
            assignment.id, objective_score=9.9, subjective_notes="Great", as_of=date(2026, 3, 1)
        )


def test_closure_allowed_after_minimum_elapsed_period(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    closed = _close(service, assignment.id, score=4.5, notes="Strong quarter")

    assert closed.state == AssignmentState.CLOSED
    assert closed.closed_reason == "completed"


def test_cannot_close_an_already_closed_assignment(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))
    _close(service, assignment.id)

    with pytest.raises(TransitionDenied):
        service.close_assignment(
            assignment.id, objective_score=4.0, subjective_notes="Again?", as_of=date(2026, 4, 1)
        )


def test_concurrent_close_from_stale_copy_is_rejected(service):
    """Simulates two browser tabs: both read the same assignment, one
    closes it, the other's stale copy must be rejected, not silently
    overwrite the first close."""
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))
    service.record_goal_setting(assignment.id, "Ship feature X")

    tab_a_view = service._repo.get(assignment.id)
    tab_b_view = service._repo.get(assignment.id)

    tab_a_view.state = AssignmentState.CLOSED
    service._repo.close_with_record(
        tab_a_view,
        ClosureRecord(assignment_id=assignment.id, objective_score=4.0, subjective_notes="First"),
    )

    tab_b_view.state = AssignmentState.CLOSED
    with pytest.raises(ConcurrentModification):
        service._repo.close_with_record(
            tab_b_view,
            ClosureRecord(
                assignment_id=assignment.id, objective_score=2.0, subjective_notes="Second"
            ),
        )


def test_withdraw_assignment_needs_no_score(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    withdrawn = service.withdraw_assignment(assignment.id, notes="Left the program")

    assert withdrawn.state == AssignmentState.CLOSED
    assert withdrawn.closed_reason == "withdrawn"
    assert withdrawn.closure_note == "Left the program"
    assert service._repo.get_closure_record(assignment.id) is None


def test_withdraw_ignores_minimum_elapsed_period(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    # Day 2 — nowhere near the 30-day closure minimum, must still work
    withdrawn = service.withdraw_assignment(assignment.id)
    assert withdrawn.state == AssignmentState.CLOSED


def test_reassign_all_from_departing_manager(service):
    agent_a, agent_b = uuid4(), uuid4()
    old_manager, new_manager = uuid4(), uuid4()
    assignment_a = service.create_assignment(agent_a, old_manager, date(2026, 1, 1))
    assignment_b = service.create_assignment(agent_b, old_manager, date(2026, 1, 1))

    new_assignments = service.reassign_all_from_departing_manager(
        old_manager, new_manager, notes="Alex left the company", as_of=date(2026, 3, 1)
    )

    assert service._repo.get(assignment_a.id).state == AssignmentState.CLOSED
    assert service._repo.get(assignment_a.id).closed_reason == "manager_departed"
    assert service._repo.get(assignment_b.id).state == AssignmentState.CLOSED
    assert {a.manager_id for a in new_assignments} == {new_manager}
    assert {a.agent_id for a in new_assignments} == {agent_a, agent_b}
    assert all(a.start_date == date(2026, 3, 1) for a in new_assignments)


def test_reassign_rejects_same_manager_as_target(service):
    manager_id = uuid4()
    with pytest.raises(ValueError):
        service.reassign_all_from_departing_manager(manager_id, manager_id)


def test_reassign_skips_already_closed_assignments(service):
    agent_id = uuid4()
    old_manager, new_manager = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, old_manager, date(2026, 1, 1))
    _close(service, assignment.id)

    new_assignments = service.reassign_all_from_departing_manager(old_manager, new_manager)

    assert new_assignments == []


def test_cross_team_bifurcation_each_assignment_independent(service):
    agent_id = uuid4()
    manager_a, manager_b = uuid4(), uuid4()
    assignment_a = service.create_assignment(agent_id, manager_a, date(2026, 1, 1))
    assignment_b = service.create_assignment(agent_id, manager_b, date(2026, 1, 1))

    # manager_b closing their assignment must not affect manager_a's
    _close(service, assignment_b.id, score=3.5, notes="Fine")

    assert service._repo.get(assignment_a.id).state == AssignmentState.ACTIVE
    assert service._repo.get(assignment_b.id).state == AssignmentState.CLOSED


def test_reverse_feedback_denied_before_minimum_elapsed_period(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    with pytest.raises(TransitionDenied, match="30 days"):
        service.record_reverse_feedback(
            assignment.id, "Too soon to say", as_of=date(2026, 1, 10)
        )


def test_reverse_feedback_allowed_after_minimum_elapsed_independent_of_state(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))

    feedback = service.record_reverse_feedback(
        assignment.id, "Great mentor, very supportive", as_of=date(2026, 3, 1)
    )

    assert feedback.assignment_id == assignment.id


def test_list_overdue_goal_setting_reflects_reminder_need(service):
    agent_id, manager_a, manager_b = uuid4(), uuid4(), uuid4()
    overdue = service.create_assignment(agent_id, manager_a, date(2026, 1, 1))
    on_time = service.create_assignment(agent_id, manager_b, date(2026, 1, 1))
    service.record_goal_setting(on_time.id, "Ship feature X")

    overdue_list = service.list_overdue_goal_setting(older_than_days=14, as_of=date(2026, 2, 1))

    assert [a.id for a in overdue_list] == [overdue.id]


def test_list_overdue_closure_reflects_managers_who_never_close(service):
    agent_id, manager_id = uuid4(), uuid4()
    assignment = service.create_assignment(agent_id, manager_id, date(2026, 1, 1))
    service.record_goal_setting(assignment.id, "Ship feature X")

    not_yet = service.list_overdue_closure(as_of=date(2026, 2, 1))  # 31 days, under 2x30
    overdue = service.list_overdue_closure(as_of=date(2026, 4, 1))  # ~90 days, over 2x30

    assert not_yet == []
    assert [a.id for a in overdue] == [assignment.id]
