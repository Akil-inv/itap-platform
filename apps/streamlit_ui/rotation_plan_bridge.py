"""Bridges Assignment closure to the linked Rotation Plan stage — the one
place in the app allowed to know about both `assignment` and
`rotation_plan`, since neither capability imports the other (see
docs/architecture.md).

Call `advance_linked_stage_if_closed` right after any action that closes
an Assignment (normal close, withdrawal, manager handoff). It is a no-op
whenever there's nothing to do: the Assignment isn't linked to any
Enrollment's current stage, or that stage was already the plan's last
one. If the plan's new stage has a default Manager
(`RotationPlan.default_stage_managers`), a fresh Assignment is created
under that Manager and linked to the new stage in the same action — so
the common path needs no admin click at all, only a plan that was set up
with default Managers per stage. Failures here are swallowed rather than
raised — this is a convenience side effect, and it must never turn a
successful Assignment closure into a visible error for the person who
just closed it.
"""
from __future__ import annotations

from uuid import UUID

from assignment.clock import today
from assignment.domain import AssignmentNotFound, DuplicateAssignment


def advance_linked_stage_if_closed(services, assignment_id: UUID) -> None:
    try:
        assignment = services.assignment_repo.get(assignment_id)
    except AssignmentNotFound:
        return

    enrollments = services.rotation_plan_repo.list_enrollments_for_agent(assignment.agent_id)
    for enrollment in enrollments:
        if enrollment.current_assignment_id != assignment_id:
            continue
        try:
            plan = services.rotation_plan_repo.get_plan(enrollment.plan_id)
            if enrollment.current_stage_index >= plan.stage_count - 1:
                continue

            new_stage_index = enrollment.current_stage_index + 1
            new_manager_id = plan.default_stage_managers.get(new_stage_index)
            new_assignment_id = None
            if new_manager_id is not None:
                try:
                    new_assignment = services.assignment_service.create_assignment(
                        agent_id=assignment.agent_id,
                        manager_id=new_manager_id,
                        start_date=today(),
                    )
                    new_assignment_id = new_assignment.id
                except (DuplicateAssignment, ValueError):
                    # The Agent already has an active Assignment with that
                    # Manager, or something else about the new one is
                    # invalid — advance the stage anyway, unlinked, same
                    # as a stage with no default Manager at all.
                    new_assignment_id = None

            services.rotation_plan_service.advance_stage(
                enrollment.id, assignment_id=new_assignment_id
            )
        except Exception:  # noqa: BLE001 — deliberate: see module docstring,
            # "Failures here are swallowed rather than raised". This
            # convenience side effect must never turn a successful
            # Assignment closure into a visible error.
            return
