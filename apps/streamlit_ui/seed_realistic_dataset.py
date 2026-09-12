"""One-off script that populates a realistic-scale ITAP dataset through the
real service layer (not raw SQL) — every Party and Assignment created here
goes through the same validation, RBAC, and rule-engine paths a real user
action would, so it "sticks" exactly the way manually clicking through the
UI would.

Creates:
  - 4 ITAP Admins (Functional Owners)
  - 15 Line Managers across 5 functions (3 managers per function)
  - 40 Intern/Staff Agents, onboarded in 5 batches of 7-9 people each,
    scattered across roughly 3 months (early Jan through mid March 2026)
  - One associate withdrawn partway through their rotation, simulating
    someone leaving mid-program

Idempotent: matches existing Parties by exact display_name, so running
this twice reuses people instead of duplicating them, and re-creating an
assignment that already exists (DuplicateAssignment) is silently skipped.

Run against whatever database the app itself is configured to use (by
default `sqlite:///itap.db`, same as `streamlit run app.py` — set
DATABASE_URL to point elsewhere, e.g. a shared Postgres instance):

    cd apps/streamlit_ui
    source .venv/bin/activate
    python seed_realistic_dataset.py
"""
from __future__ import annotations

from datetime import date

from assignment.domain import DuplicateAssignment
from party_identity.domain import Party
from services import get_services

ADMIN_NAMES = ["Priyanka Rao", "Marcus Webb", "Fatima Noor", "David Chen"]

FUNCTIONS: dict[str, list[str]] = {
    "Engineering": ["Alex Rivera", "Sofia Martins", "Ken Watanabe"],
    "Design": ["Bailey Chen", "Elena Petrov", "Omar Farouk"],
    "Data & Analytics": ["Priti Deshmukh", "Liam O'Connor", "Ngozi Adeyemi"],
    "Product": ["Jordan Ames", "Ana Beatriz Silva", "Tariq Hassan"],
    "Operations": ["Noor Malik", "Hana Kobayashi", "Carlos Medina"],
}

_FIRST_NAMES = [
    "Casey", "Dana", "Riya", "Marcus", "Wei", "Sofia", "Jordan", "Emma", "Liu", "Aisha",
    "Diego", "Grace", "Hassan", "Ines", "Jamal", "Keiko", "Leo", "Maya", "Nathan", "Olga",
    "Paulo", "Quinn", "Rosa", "Sam", "Tara", "Umar", "Vera", "Will", "Xin", "Yusuf",
    "Zara", "Bianca", "Chidi", "Deepak", "Elif", "Frank", "Gita", "Hugo", "Ivy", "Jack",
]
_LAST_NAMES = [
    "Nolan", "Whitfield", "Sen", "Lin", "Zhang", "Patel", "Blake", "Ortiz", "Feng", "Khan",
    "Alvarez", "Kim", "Farah", "Duarte", "Haddad", "Suzuki", "Bennett", "Singh", "Brooks", "Ivanova",
    "Silva", "Reyes", "Moreno", "Walsh", "Iqbal", "Bello", "Novak", "Turner", "Wu", "Demir",
    "Haile", "Costa", "Okafor", "Mehta", "Yildiz", "Sullivan", "Rao", "Fischer", "Callahan", "Park",
]
ASSOCIATE_NAMES = [f"{f} {l}" for f, l in zip(_FIRST_NAMES, _LAST_NAMES)]
assert len(ASSOCIATE_NAMES) == 40
assert len(set(ASSOCIATE_NAMES)) == 40

# Onboarding batches: (start_date, headcount). Sums to 40, spans roughly
# three months, each batch onboarded on a single shared day.
BATCHES = [
    (date(2026, 1, 6), 8),
    (date(2026, 1, 22), 7),
    (date(2026, 2, 10), 9),
    (date(2026, 2, 26), 8),
    (date(2026, 3, 16), 8),
]
assert sum(count for _, count in BATCHES) == 40

# The associate who leaves partway through — index into ASSOCIATE_NAMES,
# picked from the first (earliest) batch so there's real elapsed time
# before the withdrawal.
LEAVER_INDEX = 2
LEAVER_NOTE = "Left the company for an external opportunity."


def get_or_create(services, party_type: str, name: str, attributes: dict | None = None) -> Party:
    for existing in services.party_repo.list_by_type(party_type):
        if existing.display_name == name:
            return existing
    party = Party(party_type=party_type, display_name=name, attributes=attributes or {})
    services.party_repo.add(party)
    return party


def main() -> None:
    services = get_services()

    admins = [get_or_create(services, "functional_owner", name) for name in ADMIN_NAMES]
    print(f"ITAP Admins: {len(admins)}")

    managers: list[Party] = []
    for function_name, names in FUNCTIONS.items():
        for name in names:
            managers.append(
                get_or_create(services, "manager", name, {"function": function_name})
            )
    print(f"Managers: {len(managers)} across {len(FUNCTIONS)} functions")

    associates = [get_or_create(services, "agent", name) for name in ASSOCIATE_NAMES]
    print(f"Associates: {len(associates)}")

    created, skipped = 0, 0
    manager_cycle_index = 0
    leaver_assignment_id = None
    overall_index = 0
    for batch_start, headcount in BATCHES:
        for _ in range(headcount):
            associate = associates[overall_index]
            manager = managers[manager_cycle_index % len(managers)]
            manager_cycle_index += 1

            # Idempotency: skip if this Agent+Manager pair already has ANY
            # Assignment (active or closed) — relying only on the service's
            # own DuplicateAssignment check isn't enough here, since that
            # only guards against a duplicate *active* one, and the leaver
            # ends up closed after the first run.
            already_paired = any(
                a.manager_id == manager.id
                for a in services.assignment_repo.list_by_agent(associate.id)
            )
            if already_paired:
                skipped += 1
                if overall_index == LEAVER_INDEX:
                    existing = [
                        a
                        for a in services.assignment_repo.list_by_agent(associate.id)
                        if a.manager_id == manager.id
                    ]
                    leaver_assignment_id = existing[0].id
                overall_index += 1
                continue

            try:
                assignment = services.assignment_service.create_assignment(
                    agent_id=associate.id, manager_id=manager.id, start_date=batch_start
                )
                created += 1
                if overall_index == LEAVER_INDEX:
                    leaver_assignment_id = assignment.id
            except DuplicateAssignment:
                skipped += 1
            overall_index += 1

    print(f"Assignments: {created} created, {skipped} already existed")

    leaver_name = ASSOCIATE_NAMES[LEAVER_INDEX]
    if leaver_assignment_id is not None:
        current = services.assignment_repo.get(leaver_assignment_id)
        if current.state.value == "active":
            services.assignment_service.withdraw_assignment(
                leaver_assignment_id, notes=LEAVER_NOTE
            )
            print(f"Withdrew {leaver_name}'s assignment: {LEAVER_NOTE!r}")
        else:
            print(f"{leaver_name}'s assignment was already withdrawn in a prior run.")

    print("Seed complete.")


if __name__ == "__main__":
    main()
