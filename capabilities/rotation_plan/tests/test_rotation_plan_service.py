from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from rotation_plan.domain import (
    AlreadyEnrolled,
    NoNextStage,
    RotationPlanNotFound,
    StageIndexOutOfRange,
)
from rotation_plan.service import RotationPlanService


@pytest.fixture
def service(rotation_plan_repo):
    # Parametrized over both adapters (see conftest.py) — the SQL adapter
    # round-trips datetimes through SQLite without tzinfo, which caught a
    # real naive/aware subtraction bug in progress_value() that an
    # in-memory-only fixture would have missed entirely.
    return RotationPlanService(rotation_plan_repo)


def test_create_plan(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data", "Product"])
    assert plan.stage_count == 3
    assert plan.weeks_per_stage == 8


def test_enroll_starts_at_stage_zero(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"])
    enrollment = service.enroll(plan.id, uuid4())
    assert enrollment.current_stage_index == 0


def test_enroll_in_missing_plan_raises(service):
    with pytest.raises(RotationPlanNotFound):
        service.enroll(uuid4(), uuid4())


def test_double_enrollment_raises(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"])
    agent_id = uuid4()
    service.enroll(plan.id, agent_id)
    with pytest.raises(AlreadyEnrolled):
        service.enroll(plan.id, agent_id)


def test_advance_stage_moves_to_next(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data", "Product"])
    enrollment = service.enroll(plan.id, uuid4())

    advanced = service.advance_stage(enrollment.id)

    assert advanced.current_stage_index == 1


def test_advance_stage_resets_stage_started_at(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"])
    enrollment = service.enroll(plan.id, uuid4())
    later = datetime.now(timezone.utc) + timedelta(days=30)

    advanced = service.advance_stage(enrollment.id, as_of=later)

    # The SQL adapter drops tzinfo on round-trip (SQLite has no tz-aware
    # storage) — compare naive-vs-naive so this test passes against both
    # adapters rather than asserting exact aware-datetime equality.
    got = advanced.stage_started_at.replace(tzinfo=None)
    assert got == later.replace(tzinfo=None)


def test_advance_past_last_stage_raises(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"])
    enrollment = service.enroll(plan.id, uuid4())
    service.advance_stage(enrollment.id)  # now at last stage (index 1)

    with pytest.raises(NoNextStage):
        service.advance_stage(enrollment.id)


def test_progress_value_at_start_of_stage(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"], weeks_per_stage=8)
    enrollment = service.enroll(plan.id, uuid4())

    assert service.progress_value(enrollment, plan, as_of=enrollment.stage_started_at) == 0.0


def test_progress_value_partway_through_stage(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"], weeks_per_stage=8)
    enrollment = service.enroll(plan.id, uuid4())
    halfway = enrollment.stage_started_at + timedelta(weeks=4)

    value = service.progress_value(enrollment, plan, as_of=halfway)

    assert 0.45 < value < 0.55


def test_progress_value_clamped_when_stage_overdue(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"], weeks_per_stage=8)
    enrollment = service.enroll(plan.id, uuid4())
    way_late = enrollment.stage_started_at + timedelta(weeks=52)

    value = service.progress_value(enrollment, plan, as_of=way_late)

    assert value < 1.0


def test_progress_value_with_no_as_of_does_not_raise(service):
    # Regression: SQLite drops tzinfo on round-trip, so a naive
    # stage_started_at read back via the SQL adapter used to raise
    # "can't subtract offset-naive and offset-aware datetimes" against the
    # aware `datetime.now(timezone.utc)` this uses when `as_of` is omitted.
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"])
    enrollment = service.enroll(plan.id, uuid4())

    value = service.progress_value(enrollment, plan)

    assert value >= 0.0


def test_progress_value_reflects_current_stage_index(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data", "Product"], weeks_per_stage=8)
    enrollment = service.enroll(plan.id, uuid4())
    advanced = service.advance_stage(enrollment.id)

    value = service.progress_value(advanced, plan, as_of=advanced.stage_started_at)

    assert value == 1.0


def test_enroll_can_link_the_starting_assignment(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"])
    assignment_id = uuid4()

    enrollment = service.enroll(plan.id, uuid4(), assignment_id=assignment_id)

    assert enrollment.stage_assignments == {0: assignment_id}
    assert enrollment.current_assignment_id == assignment_id


def test_enroll_without_assignment_id_leaves_it_unlinked(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"])
    enrollment = service.enroll(plan.id, uuid4())
    assert enrollment.current_assignment_id is None


def test_advance_stage_can_link_the_new_assignment(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"])
    enrollment = service.enroll(plan.id, uuid4())
    new_assignment_id = uuid4()

    advanced = service.advance_stage(enrollment.id, assignment_id=new_assignment_id)

    assert advanced.current_assignment_id == new_assignment_id
    assert advanced.stage_assignments == {1: new_assignment_id}


def test_advance_stage_preserves_earlier_stage_links(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data", "Product"])
    first_assignment = uuid4()
    enrollment = service.enroll(plan.id, uuid4(), assignment_id=first_assignment)

    advanced = service.advance_stage(enrollment.id)

    assert advanced.stage_assignments == {0: first_assignment}
    assert advanced.current_assignment_id is None


def test_link_assignment_sets_the_given_stage(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data", "Product"])
    enrollment = service.enroll(plan.id, uuid4())
    assignment_id = uuid4()

    updated = service.link_assignment(enrollment.id, 0, assignment_id)

    assert updated.stage_assignments == {0: assignment_id}


def test_link_assignment_can_target_a_non_current_stage(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data", "Product"])
    enrollment = service.enroll(plan.id, uuid4())
    past_assignment = uuid4()

    # Backfilling a link for an already-completed stage after the fact.
    updated = service.link_assignment(enrollment.id, 0, past_assignment)

    assert updated.stage_assignments[0] == past_assignment
    assert updated.current_stage_index == 0  # linking doesn't move the stage


def test_link_assignment_rejects_out_of_range_stage(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"])
    enrollment = service.enroll(plan.id, uuid4())

    with pytest.raises(StageIndexOutOfRange):
        service.link_assignment(enrollment.id, 5, uuid4())


def test_create_plan_with_default_stage_managers(service):
    manager_id = uuid4()
    plan = service.create_plan(
        "Engineering Foundations Track", ["Platform", "Data"],
        default_stage_managers={0: manager_id},
    )
    assert plan.default_stage_managers == {0: manager_id}


def test_set_default_manager(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data", "Product"])
    manager_id = uuid4()

    updated = service.set_default_manager(plan.id, 1, manager_id)

    assert updated.default_stage_managers == {1: manager_id}


def test_set_default_manager_can_be_changed(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"])
    first_manager, second_manager = uuid4(), uuid4()

    service.set_default_manager(plan.id, 0, first_manager)
    updated = service.set_default_manager(plan.id, 0, second_manager)

    assert updated.default_stage_managers == {0: second_manager}


def test_set_default_manager_none_clears_it(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"])
    service.set_default_manager(plan.id, 0, uuid4())

    updated = service.set_default_manager(plan.id, 0, None)

    assert updated.default_stage_managers == {}


def test_set_default_manager_rejects_out_of_range_stage(service):
    plan = service.create_plan("Engineering Foundations Track", ["Platform", "Data"])

    with pytest.raises(StageIndexOutOfRange):
        service.set_default_manager(plan.id, 9, uuid4())
