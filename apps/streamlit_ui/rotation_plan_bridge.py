"""Bridges Assignment closure to the linked Rotation Plan stage — the one
place in the app allowed to know about both `assignment` and
`rotation_plan`, since neither capability imports the other (see
docs/architecture.md).

Call `advance_linked_stage_if_closed` right after any action that closes
an Assignment (normal close, withdrawal, manager handoff). It is a no-op
whenever there's nothing to do: the Assignment isn't linked to any
Enrollment's current stage, or that stage was already the plan's last
one. Failures here are swallowed rather than raised — this is a
convenience side effect, and it must never turn a successful Assignment
closure into a visible error for the person who just closed it.
"""
from __future__ import annotations

from uuid import UUID


def advance_linked_stage_if_closed(services, assignment_id: UUID) -> None:
    try:
        assignment = services.assignment_repo.get(assignment_id)
    except Exception:
        return

    enrollments = services.rotation_plan_repo.list_enrollments_for_agent(assignment.agent_id)
    for enrollment in enrollments:
        if enrollment.current_assignment_id != assignment_id:
            continue
        try:
            plan = services.rotation_plan_repo.get_plan(enrollment.plan_id)
            if enrollment.current_stage_index < plan.stage_count - 1:
                services.rotation_plan_service.advance_stage(enrollment.id)
        except Exception:
            return
