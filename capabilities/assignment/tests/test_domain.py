from datetime import date
from uuid import uuid4

import pytest

from assignment.domain import Assignment, ClosureRecord


def test_assignment_rejects_end_date_before_start_date():
    with pytest.raises(ValueError):
        Assignment(
            agent_id=uuid4(),
            manager_id=uuid4(),
            start_date=date(2026, 6, 1),
            end_date=date(2026, 1, 1),
        )


def test_assignment_allows_end_date_equal_to_start_date():
    # a zero-length window is unusual but not invalid — creation doesn't
    # imply a minimum duration, only that end can't precede start
    Assignment(
        agent_id=uuid4(),
        manager_id=uuid4(),
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 1),
    )


@pytest.mark.parametrize("score", [-0.1, 5.1, 100])
def test_closure_record_rejects_out_of_range_score(score):
    with pytest.raises(ValueError):
        ClosureRecord(assignment_id=uuid4(), objective_score=score, subjective_notes="x")


@pytest.mark.parametrize("score", [0.0, 2.5, 5.0])
def test_closure_record_accepts_in_range_score(score):
    ClosureRecord(assignment_id=uuid4(), objective_score=score, subjective_notes="x")
