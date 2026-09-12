from uuid import uuid4

import pytest

from rotation_plan.domain import (
    ConcurrentModification,
    Enrollment,
    EnrollmentNotFound,
    RotationPlan,
    RotationPlanNotFound,
)


def _make_plan(**overrides):
    defaults = dict(name="Engineering Foundations Track", stage_names=["Platform", "Data", "Product"])
    defaults.update(overrides)
    return RotationPlan(**defaults)


def test_add_and_get_plan_round_trips(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)

    fetched = rotation_plan_repo.get_plan(plan.id)

    assert fetched.id == plan.id
    assert fetched.name == plan.name
    assert fetched.stage_names == plan.stage_names
    assert fetched.weeks_per_stage == plan.weeks_per_stage


def test_get_missing_plan_raises(rotation_plan_repo):
    with pytest.raises(RotationPlanNotFound):
        rotation_plan_repo.get_plan(uuid4())


def test_list_plans(rotation_plan_repo):
    a = _make_plan(name="Engineering Foundations Track")
    b = _make_plan(name="Design Foundations Track", stage_names=["Design", "Research"])
    rotation_plan_repo.add_plan(a)
    rotation_plan_repo.add_plan(b)

    names = {p.name for p in rotation_plan_repo.list_plans()}
    assert names == {"Engineering Foundations Track", "Design Foundations Track"}


def test_add_and_get_enrollment_round_trips(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)
    agent_id = uuid4()
    enrollment = Enrollment(plan_id=plan.id, agent_id=agent_id)
    rotation_plan_repo.add_enrollment(enrollment)

    fetched = rotation_plan_repo.get_enrollment(enrollment.id)
    assert fetched.plan_id == plan.id
    assert fetched.agent_id == agent_id
    assert fetched.current_stage_index == 0


def test_get_missing_enrollment_raises(rotation_plan_repo):
    with pytest.raises(EnrollmentNotFound):
        rotation_plan_repo.get_enrollment(uuid4())


def test_get_enrollment_for_agent(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)
    agent_id = uuid4()
    enrollment = Enrollment(plan_id=plan.id, agent_id=agent_id)
    rotation_plan_repo.add_enrollment(enrollment)

    assert rotation_plan_repo.get_enrollment_for_agent(agent_id, plan.id).id == enrollment.id
    assert rotation_plan_repo.get_enrollment_for_agent(uuid4(), plan.id) is None


def test_list_enrollments_for_plan_and_agent(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)
    agent_a, agent_b = uuid4(), uuid4()
    e1 = Enrollment(plan_id=plan.id, agent_id=agent_a)
    e2 = Enrollment(plan_id=plan.id, agent_id=agent_b)
    rotation_plan_repo.add_enrollment(e1)
    rotation_plan_repo.add_enrollment(e2)

    assert {e.id for e in rotation_plan_repo.list_enrollments_for_plan(plan.id)} == {e1.id, e2.id}
    assert [e.id for e in rotation_plan_repo.list_enrollments_for_agent(agent_a)] == [e1.id]


def test_update_enrollment_persists_stage_change(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)
    enrollment = Enrollment(plan_id=plan.id, agent_id=uuid4())
    rotation_plan_repo.add_enrollment(enrollment)

    enrollment.current_stage_index = 1
    rotation_plan_repo.update_enrollment(enrollment)

    assert rotation_plan_repo.get_enrollment(enrollment.id).current_stage_index == 1


def test_update_enrollment_rejects_stale_version(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)
    enrollment = Enrollment(plan_id=plan.id, agent_id=uuid4())
    rotation_plan_repo.add_enrollment(enrollment)

    copy_a = rotation_plan_repo.get_enrollment(enrollment.id)
    copy_b = rotation_plan_repo.get_enrollment(enrollment.id)

    copy_a.current_stage_index = 1
    rotation_plan_repo.update_enrollment(copy_a)

    copy_b.current_stage_index = 2
    with pytest.raises(ConcurrentModification):
        rotation_plan_repo.update_enrollment(copy_b)


def test_update_missing_enrollment_raises(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)
    phantom = Enrollment(plan_id=plan.id, agent_id=uuid4())
    with pytest.raises(EnrollmentNotFound):
        rotation_plan_repo.update_enrollment(phantom)


def test_stage_assignments_round_trips(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)
    assignment_id = uuid4()
    enrollment = Enrollment(
        plan_id=plan.id, agent_id=uuid4(), stage_assignments={0: assignment_id}
    )
    rotation_plan_repo.add_enrollment(enrollment)

    fetched = rotation_plan_repo.get_enrollment(enrollment.id)
    assert fetched.stage_assignments == {0: assignment_id}
    assert fetched.current_assignment_id == assignment_id


def test_stage_assignments_default_to_empty(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)
    enrollment = Enrollment(plan_id=plan.id, agent_id=uuid4())
    rotation_plan_repo.add_enrollment(enrollment)

    assert rotation_plan_repo.get_enrollment(enrollment.id).stage_assignments == {}


def test_update_enrollment_persists_stage_assignments(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)
    enrollment = Enrollment(plan_id=plan.id, agent_id=uuid4())
    rotation_plan_repo.add_enrollment(enrollment)

    assignment_id = uuid4()
    enrollment.stage_assignments = {0: assignment_id}
    rotation_plan_repo.update_enrollment(enrollment)

    assert rotation_plan_repo.get_enrollment(enrollment.id).stage_assignments == {
        0: assignment_id
    }


def test_default_stage_managers_round_trips(rotation_plan_repo):
    manager_id = uuid4()
    plan = _make_plan(default_stage_managers={0: manager_id})
    rotation_plan_repo.add_plan(plan)

    fetched = rotation_plan_repo.get_plan(plan.id)
    assert fetched.default_stage_managers == {0: manager_id}


def test_default_stage_managers_default_to_empty(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)
    assert rotation_plan_repo.get_plan(plan.id).default_stage_managers == {}


def test_update_plan_persists_default_stage_managers(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)

    manager_id = uuid4()
    plan.default_stage_managers = {1: manager_id}
    rotation_plan_repo.update_plan(plan)

    assert rotation_plan_repo.get_plan(plan.id).default_stage_managers == {1: manager_id}


def test_update_plan_rejects_stale_version(rotation_plan_repo):
    plan = _make_plan()
    rotation_plan_repo.add_plan(plan)

    copy_a = rotation_plan_repo.get_plan(plan.id)
    copy_b = rotation_plan_repo.get_plan(plan.id)

    copy_a.default_stage_managers = {0: uuid4()}
    rotation_plan_repo.update_plan(copy_a)

    copy_b.default_stage_managers = {1: uuid4()}
    with pytest.raises(ConcurrentModification):
        rotation_plan_repo.update_plan(copy_b)


def test_update_missing_plan_raises(rotation_plan_repo):
    plan = _make_plan()
    with pytest.raises(RotationPlanNotFound):
        rotation_plan_repo.update_plan(plan)
