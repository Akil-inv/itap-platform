import pytest

from rotation_plan.domain import RotationPlan


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
