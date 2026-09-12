"""App-layer test for rotation_plan_bridge.py: closing an Assignment that's
linked to an Enrollment's current stage should auto-advance that stage.
Uses `withdraw_assignment` (ungated — no min-elapsed-days, no goal-setting
requirement) so the test doesn't need to fake the passage of time. Run
directly: `python test_rotation_plan_bridge.py`.
"""
import os
from datetime import date

os.environ["DATABASE_URL"] = "sqlite:///./test_rotation_plan_bridge.db"

import rotation_plan_bridge
from party_identity.domain import Party
from services import get_services

services = get_services()

agent = Party(party_type="agent", display_name="Riya")
manager = Party(party_type="manager", display_name="Sam")
services.party_repo.add(agent)
services.party_repo.add(manager)

assignment = services.assignment_service.create_assignment(
    agent_id=agent.id, manager_id=manager.id, start_date=date(2026, 1, 1)
)

plan = services.rotation_plan_service.create_plan(
    "Engineering Foundations Track", ["Platform", "Data", "Product"]
)
enrollment = services.rotation_plan_service.enroll(
    plan.id, agent.id, assignment_id=assignment.id
)
assert enrollment.current_stage_index == 0
assert enrollment.current_assignment_id == assignment.id

# --- closing the linked assignment advances the stage ---

services.assignment_service.withdraw_assignment(assignment.id, notes="early exit")
rotation_plan_bridge.advance_linked_stage_if_closed(services, assignment.id)

advanced = services.rotation_plan_repo.get_enrollment(enrollment.id)
assert advanced.current_stage_index == 1, advanced
print("Closing a linked Assignment advances the Enrollment's stage: OK")

# --- advancing past the last stage is a no-op, not an error ---

services.rotation_plan_service.advance_stage(enrollment.id)  # now at stage 2, the last one
last_stage_enrollment = services.rotation_plan_repo.get_enrollment(enrollment.id)
assert last_stage_enrollment.current_stage_index == 2

second_assignment = services.assignment_service.create_assignment(
    agent_id=agent.id, manager_id=manager.id, start_date=date(2026, 6, 1)
)
services.rotation_plan_service.link_assignment(enrollment.id, 2, second_assignment.id)
services.assignment_service.withdraw_assignment(second_assignment.id)
rotation_plan_bridge.advance_linked_stage_if_closed(services, second_assignment.id)  # must not raise

final = services.rotation_plan_repo.get_enrollment(enrollment.id)
assert final.current_stage_index == 2, "Already at the last stage — nothing to advance to"
print("Closing an Assignment linked to the last stage is a no-op: OK")

# --- closing an Assignment with no plan link at all is also a no-op ---

unrelated_agent = Party(party_type="agent", display_name="Jordan")
services.party_repo.add(unrelated_agent)
unrelated_assignment = services.assignment_service.create_assignment(
    agent_id=unrelated_agent.id, manager_id=manager.id, start_date=date(2026, 1, 1)
)
services.assignment_service.withdraw_assignment(unrelated_assignment.id)
rotation_plan_bridge.advance_linked_stage_if_closed(services, unrelated_assignment.id)  # must not raise
print("Closing an unlinked Assignment is a no-op: OK")

# --- a stage with a default Manager gets a new Assignment auto-created and linked ---

agent2 = Party(party_type="agent", display_name="Marcus")
manager_a = Party(party_type="manager", display_name="Priti")
manager_b = Party(party_type="manager", display_name="Devika")
services.party_repo.add(agent2)
services.party_repo.add(manager_a)
services.party_repo.add(manager_b)

first_assignment = services.assignment_service.create_assignment(
    agent_id=agent2.id, manager_id=manager_a.id, start_date=date(2026, 1, 1)
)
plan2 = services.rotation_plan_service.create_plan(
    "Design Foundations Track",
    ["Product Design", "Research"],
    default_stage_managers={1: manager_b.id},
)
enrollment2 = services.rotation_plan_service.enroll(
    plan2.id, agent2.id, assignment_id=first_assignment.id
)

services.assignment_service.withdraw_assignment(first_assignment.id)
rotation_plan_bridge.advance_linked_stage_if_closed(services, first_assignment.id)

advanced2 = services.rotation_plan_repo.get_enrollment(enrollment2.id)
assert advanced2.current_stage_index == 1, advanced2
new_assignment_id = advanced2.current_assignment_id
assert new_assignment_id is not None, "Expected an auto-created Assignment linked to stage 2"
new_assignment = services.assignment_repo.get(new_assignment_id)
assert new_assignment.manager_id == manager_b.id
assert new_assignment.agent_id == agent2.id
assert new_assignment.state.value == "active"
print("A stage with a default Manager gets a new Assignment auto-created and linked: OK")

# --- a stage with no default Manager just advances, unlinked (existing behavior) ---

services.assignment_service.withdraw_assignment(new_assignment_id)
rotation_plan_bridge.advance_linked_stage_if_closed(services, new_assignment_id)
final2 = services.rotation_plan_repo.get_enrollment(enrollment2.id)
assert final2.current_stage_index == 1, "Already at the last stage of plan2"
print("A stage with no next stage still doesn't auto-create anything: OK")

os.remove("test_rotation_plan_bridge.db")
print("ALL ROTATION PLAN BRIDGE TESTS PASSED")
