"""Shared demo fixture for the AppTest-based UI test scripts
(smoke_test.py, test_admin_journey_ui.py, test_manager_journey_ui.py,
test_associate_and_approvals_ui.py).

Phase 5 removed app.py's "Seed demo data" button (per
docs/associate_journey_redesign.md — trying the product and setting up a
real client now go through the exact same Bulk Setup upload path, no
special seeding code in the app itself). These test scripts still need a
small, deterministic, named fixture to assert against (Casey/Dana/
Alex/Bailey/Priya, Casey double-booked to Alex and Bailey to exercise
cross-team bifurcation) — this module recreates exactly that, calling the
service layer directly, the same way `bulk_import.apply_import` or any
other app-layer code would, rather than driving it through the UI.
"""
from __future__ import annotations

from datetime import date

from assignment.domain import AssignmentKind
from party_identity.domain import Party


def seed_basic_demo(services) -> None:
    owner = Party(party_type="functional_owner", display_name="Priya")
    manager_a = Party(party_type="manager", display_name="Alex")
    manager_b = Party(party_type="manager", display_name="Bailey")
    agent_a = Party(party_type="agent", display_name="Casey")
    agent_b = Party(party_type="agent", display_name="Dana")

    for party in (owner, manager_a, manager_b, agent_a, agent_b):
        services.party_repo.add(party)

    services.assignment_service.create_assignment(agent_a.id, manager_a.id, date(2026, 1, 1))
    services.assignment_service.create_assignment(agent_b.id, manager_b.id, date(2026, 6, 1))
    # Cross-team bifurcation demo: Casey also reports to Bailey concurrently
    # as a Secondary — the redesign's own framing of what this case is
    # going forward (docs/architecture.md, "kind" note under block 2).
    services.assignment_service.create_assignment(
        agent_a.id, manager_b.id, date(2026, 2, 1), kind=AssignmentKind.SECONDARY
    )
