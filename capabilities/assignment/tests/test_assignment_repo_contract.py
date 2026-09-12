from datetime import date
from uuid import uuid4

import pytest

from assignment.domain import (
    Assignment,
    AssignmentNotFound,
    AssignmentState,
    ClosureRecord,
    ConcurrentModification,
    GoalSetting,
    ReverseFeedback,
)


def _make_assignment(**overrides):
    defaults = dict(
        agent_id=uuid4(),
        manager_id=uuid4(),
        start_date=date(2026, 1, 1),
    )
    defaults.update(overrides)
    return Assignment(**defaults)


def test_add_and_get_round_trips(assignment_repo):
    assignment = _make_assignment()
    assignment_repo.add(assignment)

    fetched = assignment_repo.get(assignment.id)

    assert fetched.id == assignment.id
    assert fetched.agent_id == assignment.agent_id
    assert fetched.manager_id == assignment.manager_id
    assert fetched.state == AssignmentState.ACTIVE


def test_get_missing_raises(assignment_repo):
    with pytest.raises(AssignmentNotFound):
        assignment_repo.get(uuid4())


def test_update_persists_state_change(assignment_repo):
    assignment = _make_assignment()
    assignment_repo.add(assignment)

    assignment.end_date = date(2026, 6, 30)
    assignment_repo.update(assignment)

    assert assignment_repo.get(assignment.id).end_date == date(2026, 6, 30)


def test_update_rejects_stale_version(assignment_repo):
    assignment = _make_assignment()
    assignment_repo.add(assignment)

    tab_a = assignment_repo.get(assignment.id)
    tab_b = assignment_repo.get(assignment.id)

    tab_a.end_date = date(2026, 6, 1)
    assignment_repo.update(tab_a)

    tab_b.end_date = date(2026, 7, 1)
    with pytest.raises(ConcurrentModification):
        assignment_repo.update(tab_b)

    # the first (accepted) write must be what's actually stored
    assert assignment_repo.get(assignment.id).end_date == date(2026, 6, 1)


def test_close_with_record_rejects_stale_version(assignment_repo):
    assignment = _make_assignment()
    assignment_repo.add(assignment)

    tab_a = assignment_repo.get(assignment.id)
    tab_b = assignment_repo.get(assignment.id)

    tab_a.state = AssignmentState.CLOSED
    assignment_repo.close_with_record(
        tab_a, ClosureRecord(assignment_id=assignment.id, objective_score=4.0, subjective_notes="A")
    )

    tab_b.state = AssignmentState.CLOSED
    with pytest.raises(ConcurrentModification):
        assignment_repo.close_with_record(
            tab_b,
            ClosureRecord(assignment_id=assignment.id, objective_score=1.0, subjective_notes="B"),
        )


def test_closure_note_round_trips_via_update(assignment_repo):
    assignment = _make_assignment()
    assignment_repo.add(assignment)

    assignment.closed_reason = "withdrawn"
    assignment.closure_note = "Left the program early"
    assignment_repo.update(assignment)

    fetched = assignment_repo.get(assignment.id)
    assert fetched.closed_reason == "withdrawn"
    assert fetched.closure_note == "Left the program early"


def test_list_active_older_than(assignment_repo):
    old = _make_assignment(start_date=date(2026, 1, 1))
    recent = _make_assignment(start_date=date(2026, 8, 10))
    assignment_repo.add(old)
    assignment_repo.add(recent)

    result = assignment_repo.list_active_older_than(older_than_days=14, as_of=date(2026, 8, 15))

    assert [a.id for a in result] == [old.id]


def test_close_with_record_persists_both_atomically(assignment_repo):
    assignment = _make_assignment()
    assignment_repo.add(assignment)
    assignment.state = AssignmentState.CLOSED
    closure = ClosureRecord(
        assignment_id=assignment.id, objective_score=4.0, subjective_notes="Solid quarter"
    )

    assignment_repo.close_with_record(assignment, closure)

    assert assignment_repo.get(assignment.id).state == AssignmentState.CLOSED
    assert assignment_repo.get_closure_record(assignment.id).objective_score == 4.0


def test_list_all_returns_every_assignment(assignment_repo):
    first = _make_assignment()
    second = _make_assignment()
    assignment_repo.add(first)
    assignment_repo.add(second)

    assert {a.id for a in assignment_repo.list_all()} == {first.id, second.id}


def test_list_by_agent_and_manager(assignment_repo):
    agent_id, manager_id = uuid4(), uuid4()
    mine = _make_assignment(agent_id=agent_id, manager_id=manager_id)
    other = _make_assignment()
    assignment_repo.add(mine)
    assignment_repo.add(other)

    assert [a.id for a in assignment_repo.list_by_agent(agent_id)] == [mine.id]
    assert [a.id for a in assignment_repo.list_by_manager(manager_id)] == [mine.id]


def test_list_active_without_goal_setting(assignment_repo):
    overdue = _make_assignment(start_date=date(2026, 1, 1))
    has_goals = _make_assignment(start_date=date(2026, 1, 1))
    too_recent = _make_assignment(start_date=date(2026, 8, 10))
    assignment_repo.add(overdue)
    assignment_repo.add(has_goals)
    assignment_repo.add(too_recent)
    assignment_repo.add_goal_setting(GoalSetting(assignment_id=has_goals.id, goals="Learn X"))

    result = assignment_repo.list_active_without_goal_setting(
        older_than_days=14, as_of=date(2026, 8, 15)
    )

    assert [a.id for a in result] == [overdue.id]


def test_reverse_feedback_round_trips(assignment_repo):
    assignment = _make_assignment()
    assignment_repo.add(assignment)

    assignment_repo.add_reverse_feedback(
        ReverseFeedback(assignment_id=assignment.id, notes="Great mentor")
    )
    assignment_repo.add_reverse_feedback(
        ReverseFeedback(assignment_id=assignment.id, notes="Very responsive")
    )

    feedback = assignment_repo.list_reverse_feedback(assignment.id)
    assert {f.notes for f in feedback} == {"Great mentor", "Very responsive"}
