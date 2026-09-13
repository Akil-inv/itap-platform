"""Generates the downloadable demo Setup Workbook that replaces the old
"Seed demo data" button (see docs/associate_journey_redesign.md's "Client
deployment & setup data model" — "No more Seed demo data button").

This produces an .xlsx in exactly the schema `bulk_import.py` parses —
there is no separate seeding code path: trying the product means
downloading this file and uploading it through the same Bulk Setup
screen a real client's file goes through.

**Judgment call on scale**: `docs/architecture.md`/`HANDOVER_itap-platform.md`
mention a "4-admin/15-manager/40-associate" bulk-setup sample from an
earlier pass, but that generator script isn't in this repo (only the
mention of it survived). Rather than fabricate a match to numbers with no
surviving source, this script builds a fresh, reasonably-scaled dataset
in the same spirit — small enough to stay fast to import and easy to look
at in a demo, large enough to show real variety: 3 Admins, 6 Managers
(one Team each), ~18 Associates, a Skills/CCA catalog, and a **full
calendar year of rotation history per Associate** (2-3 closed, scored
Primary stints before their current one) so the tenure battery bar shows
multiple stacked segments, not just a few months.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from openpyxl import Workbook
from openpyxl.styles import Font

from bulk_import import (
    ASSIGNMENT_COLUMNS,
    ASSOCIATE_COLUMNS,
    CCA_ACTIVITY_COLUMNS,
    MANAGER_COLUMNS,
    SHEET_ADMINS,
    SHEET_ASSIGNMENTS,
    SHEET_ASSOCIATES,
    SHEET_CCA_ACTIVITIES,
    SHEET_MANAGERS,
    SHEET_SKILLS,
    ADMIN_COLUMNS,
    SKILLS_COLUMNS,
)

random.seed(42)  # deterministic demo data — same file every time it's generated

_ADMIN_NAMES = ["Priya Nair", "Sam Okafor", "Jordan Lee"]

_MANAGER_NAMES = ["Alex Rivera", "Bailey Chen", "Morgan Patel", "Taylor Novak", "Riley Osei", "Quinn Fischer"]
_TEAM_NAMES = ["Platform Team", "Design Team", "Data Team", "Product Team", "Growth Team", "Infra Team"]
_FUNCTIONS = ["Engineering", "Design", "Data", "Product", "Marketing", "Engineering"]

_FIRST_NAMES = [
    "Casey", "Dana", "Jamie", "Avery", "Rowan", "Skyler", "Emerson", "Kendall",
    "Reese", "Harper", "Elliot", "Micah", "Sage", "Blair", "Drew", "Finley",
    "Hayden", "Peyton",
]
_LAST_NAMES = ["Kim", "Torres", "Nguyen", "Adeyemi", "Brandt", "Silva", "Petrov", "Haddad"]

_SKILLS = [
    ("Communication", "Clarity and frequency of updates to the manager"),
    ("Technical Skill", "Quality and correctness of the work produced"),
    ("Ownership", "Follow-through without needing to be chased"),
    ("Python", "General-purpose scripting and application development"),
    ("SQL", "Querying and reasoning about relational data"),
    ("Data Visualization", "Turning raw data into a clear chart or dashboard"),
    ("Public Speaking", "Presenting confidently to a group"),
    ("Product Sense", "Judgment about what's worth building"),
]

_CCA_ACTIVITIES = [
    ("Hackathon", "open"),
    ("Brownbag Series", "open"),
    ("New Hire Buddy Program", "closed"),
]

_BIOS = [
    "Data-curious engineer who likes shipping small, useful things.",
    "Design-minded builder focused on making complex flows feel simple.",
    "Enjoys untangling messy data pipelines and making them boring (in a good way).",
    "Product-obsessed generalist, happiest close to the customer.",
    "Backend-leaning engineer with a growing interest in ML.",
]

_PROJECT_HIGHLIGHTS = [
    "Shipped the onboarding module ahead of schedule",
    "Automated the weekly ops report",
    "Redesigned the intern welcome kit",
    "Cut dashboard load time in half",
    "Ran the first internal hackathon",
    "Built a Slack bot for standup reminders",
]

_SUBJECTIVE_NOTES = [
    "Consistently delivered ahead of schedule; great stakeholder updates.",
    "Strong technical growth this stint; ready for more ownership.",
    "Reliable and thorough, could push harder on proactive communication.",
    "Excellent cross-team collaborator; the team will miss them.",
    "Solid, steady contributor with a good eye for detail.",
]

TODAY = date(2026, 9, 12)  # matches this session's "today" for a believable demo


def _bold_header(ws) -> None:
    for cell in ws[1]:
        cell.font = Font(bold=True)


def _autosize(ws) -> None:
    for col_cells in ws.columns:
        width = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = max(12, width + 2)


def build_demo_workbook() -> bytes:
    wb = Workbook()
    wb.remove(wb.active)

    # -- Admins --
    ws = wb.create_sheet(SHEET_ADMINS)
    ws.append(ADMIN_COLUMNS)
    _bold_header(ws)
    for name in _ADMIN_NAMES:
        email = name.lower().replace(" ", ".") + "@example.com"
        ws.append([name, email])
    _autosize(ws)

    # -- Managers (+ team_name, seeding Teams) --
    ws = wb.create_sheet(SHEET_MANAGERS)
    ws.append(MANAGER_COLUMNS)
    _bold_header(ws)
    for name, team, function in zip(_MANAGER_NAMES, _TEAM_NAMES, _FUNCTIONS):
        email = name.lower().replace(" ", ".") + "@example.com"
        ws.append([name, email, function, team])
    _autosize(ws)

    # -- Skills --
    ws = wb.create_sheet(SHEET_SKILLS)
    ws.append(SKILLS_COLUMNS)
    _bold_header(ws)
    for skill_name, description in _SKILLS:
        ws.append([skill_name, description])
    _autosize(ws)

    # -- CCA Activities --
    ws = wb.create_sheet(SHEET_CCA_ACTIVITIES)
    ws.append(CCA_ACTIVITY_COLUMNS)
    _bold_header(ws)
    cca_organizers: dict[str, str] = {}  # cca name -> organizer manager name, reused below
    for i, (cca_name, status) in enumerate(_CCA_ACTIVITIES):
        organizer = _MANAGER_NAMES[i % len(_MANAGER_NAMES)]
        organizer_email = organizer.lower().replace(" ", ".") + "@example.com"
        ws.append([cca_name, organizer, organizer_email, status])
        cca_organizers[cca_name] = organizer
    _autosize(ws)

    # -- Associates + Assignments (built together so the history is coherent) --
    assoc_ws = wb.create_sheet(SHEET_ASSOCIATES)
    assoc_ws.append(ASSOCIATE_COLUMNS)
    _bold_header(assoc_ws)

    assign_ws = wb.create_sheet(SHEET_ASSIGNMENTS)
    assign_ws.append(ASSIGNMENT_COLUMNS)
    _bold_header(assign_ws)

    used_names: set[str] = set()
    for i, first in enumerate(_FIRST_NAMES):
        last = _LAST_NAMES[i % len(_LAST_NAMES)]
        name = f"{first} {last}"
        if name in used_names:
            name = f"{first} {last} {i}"
        used_names.add(name)
        email = name.lower().replace(" ", ".") + "@example.com"

        skills = random.sample([s[0] for s in _SKILLS], k=random.randint(2, 4))
        interested_team = random.choice(_TEAM_NAMES)
        interested_cca = random.choice([c[0] for c in _CCA_ACTIVITIES])
        bio = random.choice(_BIOS)
        experience_summary = f"Prior internship experience before joining ITAP ({name})."
        highlights = "; ".join(random.sample(_PROJECT_HIGHLIGHTS, k=2))

        assoc_ws.append(
            [
                name,
                email,
                "",  # photo_filename — demo ships with no photos.zip by default
                bio,
                experience_summary,
                highlights,
                "; ".join(skills),
                interested_team,
                interested_cca,
            ]
        )

        # 2-3 closed, scored 3-4 month Primary stints working backward
        # from a randomized total tenure length, then one still-open
        # current stint — so the battery bar shows several stacked
        # segments, not just the current one. The total length varies
        # per associate (~7-21 months) rather than a fixed 365 days for
        # everyone: a fixed total made every associate's battery bar
        # show the exact same segment count, which read as a rendering
        # bug rather than the real, varied tenures it's supposed to
        # represent.
        n_past_stints = random.choice([2, 3])
        total_tenure_days = random.randint(200, 640)
        stint_length_days = total_tenure_days // (n_past_stints + 1)
        cursor = TODAY - timedelta(days=total_tenure_days)
        managers_used = random.sample(_MANAGER_NAMES, k=n_past_stints + 1)

        for stint_i in range(n_past_stints):
            manager = managers_used[stint_i]
            start = cursor
            end = start + timedelta(days=stint_length_days - 7)
            score = round(random.uniform(3.0, 5.0), 1)
            notes = random.choice(_SUBJECTIVE_NOTES)
            criteria = "Communication; Technical Skill; Ownership"
            goals = f"Contribute to {manager.split()[0]}'s team priorities for this stint"
            assign_ws.append(
                [
                    name, manager, "primary",
                    start.isoformat(), end.isoformat(),
                    goals, criteria,
                    "closed", score, notes,
                ]
            )
            cursor = end + timedelta(days=7)  # a short Available gap between stints

        # Current, still-open Primary stint.
        current_manager = managers_used[-1]
        assign_ws.append(
            [
                name, current_manager, "primary",
                cursor.isoformat(), "",
                f"Contribute to {current_manager.split()[0]}'s team priorities",
                "Communication; Technical Skill; Ownership",
                "", "", "",
            ]
        )

        # A handful of associates also carry a Secondary or CCA episode
        # on top of their Primary history, so the Portfolio's "N
        # responsibilities" badge (and its Secondary/CCA overlap detail)
        # is actually exercised by this demo dataset — see the QA note
        # around commit b8038d8: the previous version of this generator
        # only ever produced `kind=primary` rows.
        if i == 0:
            # Concurrent Secondary, under a manager who is NOT this
            # associate's current (or any past) Primary manager, running
            # alongside their still-open current Primary stint above.
            available = [m for m in _MANAGER_NAMES if m not in managers_used]
            secondary_manager = available[0] if available else _MANAGER_NAMES[0]
            secondary_start = cursor + timedelta(days=30)
            assign_ws.append(
                [
                    name, secondary_manager, "secondary",
                    secondary_start.isoformat(), "",
                    f"Support {secondary_manager.split()[0]}'s team on a cross-functional initiative",
                    "Communication; Ownership",
                    "", "", "",
                ]
            )
        elif i in (1, 2):
            # A closed, scored CCA episode. "manager_name" here is the
            # CCA's organizer/scorer (see docs/upload_inventory.md's
            # Assignments section), reusing one of the CCA Activities
            # already declared above rather than inventing a new one.
            # Picked to not collide with this associate's currently
            # active Primary manager.
            cca_name, cca_organizer = next(
                (n, o) for n, o in cca_organizers.items() if o != current_manager
            )
            cca_start = TODAY - timedelta(days=200)
            cca_end = TODAY - timedelta(days=150)
            cca_score = round(random.uniform(3.5, 5.0), 1)
            assign_ws.append(
                [
                    name, cca_organizer, "cca",
                    cca_start.isoformat(), cca_end.isoformat(),
                    f"{cca_name} participation",
                    "",
                    "closed", cca_score, random.choice(_SUBJECTIVE_NOTES),
                ]
            )

    _autosize(assoc_ws)
    _autosize(assign_ws)

    import io

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


if __name__ == "__main__":
    with open("itap_demo_dataset.xlsx", "wb") as f:
        f.write(build_demo_workbook())
    print("Wrote itap_demo_dataset.xlsx")
