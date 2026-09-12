from uuid import uuid4

import pytest

from rotation_plan.domain import Enrollment, RotationPlan


def test_plan_requires_a_name():
    with pytest.raises(ValueError):
        RotationPlan(name="  ", stage_names=["Platform", "Data"])


def test_plan_requires_at_least_two_stages():
    with pytest.raises(ValueError):
        RotationPlan(name="Engineering Track", stage_names=["Platform"])


def test_plan_rejects_blank_stage_names():
    with pytest.raises(ValueError):
        RotationPlan(name="Engineering Track", stage_names=["Platform", "  "])


def test_plan_rejects_non_positive_weeks_per_stage():
    with pytest.raises(ValueError):
        RotationPlan(
            name="Engineering Track",
            stage_names=["Platform", "Data"],
            weeks_per_stage=0,
        )


def test_stage_count():
    plan = RotationPlan(name="Engineering Track", stage_names=["Platform", "Data", "Product"])
    assert plan.stage_count == 3


def test_current_assignment_id_is_none_when_unlinked():
    enrollment = Enrollment(plan_id=uuid4(), agent_id=uuid4())
    assert enrollment.current_assignment_id is None


def test_current_assignment_id_reads_the_current_stage_only():
    assignment_a, assignment_b = uuid4(), uuid4()
    enrollment = Enrollment(
        plan_id=uuid4(),
        agent_id=uuid4(),
        current_stage_index=1,
        stage_assignments={0: assignment_a, 1: assignment_b},
    )
    assert enrollment.current_assignment_id == assignment_b
