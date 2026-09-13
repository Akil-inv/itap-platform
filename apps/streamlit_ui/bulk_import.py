"""Bulk client setup from an Excel workbook — Admins, Managers (+ Teams),
Associates (+ profile/skills/interests), Skills, CCA Activities, and
Assignments (open or already-finished/scored).

Deliberately app-layer, not domain: parsing spreadsheets isn't a
capability concern. This module's job ends at calling AssignmentService/
CatalogService/PartyRepo — same calls the UI forms already make, just
driven by rows instead of a single submit.

Import is a two-phase preview/confirm flow (`parse_workbook` then
`apply_import`), not "upload and immediately mutate the database" —
a bad file should never be able to silently create garbage.

**Phase 5 (2026-09-12) — upsert, not skip-only.** Per
docs/associate_journey_redesign.md's "Client deployment & setup data
model": every row now matches an existing record by its natural key
(email for people; team/skill/CCA name for catalogs; associate + manager
+ kind + start_date for one assignment stint) and UPDATES that record's
fields to whatever the file now says. This is a real behavior change from
the previous "match and reuse unchanged, skip a duplicate assignment"
logic — see docs/architecture.md's Phase 5 section for the full
before/after. Nothing is ever duplicated; an unmatched row still creates
a new record exactly as before.

**Judgment call — renaming a matched person.** `PartyRepo.update_attributes`
only merges the `attributes` dict; there is no port method to change a
Party's `display_name` in place. So a re-upload updates a matched
person's attributes (email, function, team_name-derived data) but not
their display name if the sheet's name column disagrees with what's on
file — adding a rename method was judged not worth it for this pass
(the natural key is the email, not the name, so this only bites a
same-person edit that also changes the "name" cell, which should be
rare); flagged in docs/architecture.md.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID

import pandas as pd
import photo_storage
from assignment.domain import AssignmentKind, DuplicateAssignment, GoalSettingFrozen
from catalog.domain import CcaStatus, InterestTargetType, SkillSource
from openpyxl import Workbook
from openpyxl.styles import Font
from party_identity.domain import Party

SHEET_ADMINS = "Admins"
SHEET_ASSOCIATES = "Associates"
SHEET_MANAGERS = "Managers"
SHEET_ASSIGNMENTS = "Assignments"
SHEET_SKILLS = "Skills"
SHEET_CCA_ACTIVITIES = "CCA Activities"

ADMIN_COLUMNS = ["name", "email"]
ASSOCIATE_COLUMNS = [
    "name",
    "email",
    "photo_filename",
    "bio",
    "experience_summary",
    "project_highlights",
    "skills",
    "interested_teams",
    "interested_ccas",
]
# "function" is optional (e.g. "Engineering", "Design") — a grouping label
# stored on Party.attributes["function"]. "team_name" (new, Phase 5) seeds
# the Teams catalog directly off this sheet — one Team per Manager, per
# the redesign spec's "one-team-one-manager for MVP" resolution.
MANAGER_COLUMNS = ["name", "email", "function", "team_name"]
ASSIGNMENT_COLUMNS = [
    "associate_name",
    "manager_name",
    "kind",
    "start_date",
    "end_date",
    "goals",
    "criteria",
    "status",
    "objective_score",
    "subjective_notes",
]
SKILLS_COLUMNS = ["name", "description"]
CCA_ACTIVITY_COLUMNS = ["name", "organizer_name", "organizer_email", "status"]

_EXAMPLE_ROWS = {
    SHEET_ADMINS: [["Priya", "priya@example.com"]],
    SHEET_ASSOCIATES: [
        [
            "Casey",
            "casey@example.com",
            "casey@example.com.jpg",
            "Data-curious engineer who likes shipping small, useful things.",
            "6mo backend intern at a fintech startup before joining ITAP.",
            "Built the onboarding module; automated the weekly ops report",
            "Python; SQL",
            "Platform Team",
            "Hackathon",
        ],
        ["Dana", "", "", "", "", "", "", "", ""],
    ],
    SHEET_MANAGERS: [
        ["Alex", "alex@example.com", "Engineering", "Platform Team"],
        ["Bailey", "", "Design", "Design Team"],
    ],
    SHEET_ASSIGNMENTS: [
        [
            "Casey",
            "Alex",
            "primary",
            "2026-01-01",
            "",
            "Ship the onboarding module",
            "Communication; Technical Skill; Ownership",
            "",
            "",
            "",
        ],
        [
            "Dana",
            "Bailey",
            "primary",
            "2025-01-01",
            "2025-06-30",
            "Redesign the intern welcome kit",
            "Communication; Technical Skill; Ownership",
            "closed",
            "4.2",
            "Consistently delivered ahead of schedule; great stakeholder updates.",
        ],
        # kind=secondary: a real second manager, running concurrently with
        # Casey's still-open Primary above (same associate, overlapping
        # dates, a DIFFERENT manager) — this is what the Portfolio's "N
        # responsibilities" badge counts beyond 1.
        [
            "Casey",
            "Bailey",
            "secondary",
            "2026-02-01",
            "",
            "Support the design team's onboarding revamp",
            "Communication; Ownership",
            "",
            "",
            "",
        ],
        # kind=cca: manager_name here is the CCA's organizer/scorer, not a
        # people-manager relationship — see docs/upload_inventory.md's
        # Assignments section. "Alex" matches the "Hackathon" row on the
        # CCA Activities sheet below, where Alex is that CCA's organizer.
        [
            "Dana",
            "Alex",
            "cca",
            "2025-01-15",
            "2025-03-01",
            "Hackathon entry: internal tools track",
            "",
            "closed",
            "4.6",
            "Won best-in-track; shipped a working demo solo.",
        ],
    ],
    SHEET_SKILLS: [
        ["Communication", "Clarity and frequency of updates to the manager"],
        ["Technical Skill", "Quality and correctness of the work produced"],
        ["Ownership", "Follow-through without needing to be chased"],
    ],
    SHEET_CCA_ACTIVITIES: [
        ["Hackathon", "Alex", "alex@example.com", "open"],
        ["Brownbag Series", "Bailey", "", "closed"],
    ],
}


def build_template_workbook() -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    sheets = {
        SHEET_ADMINS: ADMIN_COLUMNS,
        SHEET_ASSOCIATES: ASSOCIATE_COLUMNS,
        SHEET_MANAGERS: MANAGER_COLUMNS,
        SHEET_ASSIGNMENTS: ASSIGNMENT_COLUMNS,
        SHEET_SKILLS: SKILLS_COLUMNS,
        SHEET_CCA_ACTIVITIES: CCA_ACTIVITY_COLUMNS,
    }
    for name, columns in sheets.items():
        ws = wb.create_sheet(name)
        ws.append(columns)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for row in _EXAMPLE_ROWS.get(name, []):
            ws.append(row)
        for col_cells in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col_cells)
            ws.column_dimensions[col_cells[0].column_letter].width = max(12, width + 2)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@dataclass
class ParsedWorkbook:
    admins: list[dict[str, Any]] = field(default_factory=list)
    associates: list[dict[str, Any]] = field(default_factory=list)
    managers: list[dict[str, Any]] = field(default_factory=list)
    assignments: list[dict[str, Any]] = field(default_factory=list)
    skills: list[dict[str, Any]] = field(default_factory=list)
    cca_activities: list[dict[str, Any]] = field(default_factory=list)
    sheet_errors: list[str] = field(default_factory=list)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _clean_str(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _parse_date(value: Any) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _parse_float(value: Any) -> float | None:
    text = _clean_str(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_semicolon_list(value: Any) -> list[str]:
    text = _clean_str(value)
    if not text:
        return []
    return [c.strip() for c in text.split(";") if c.strip()]


_parse_criteria = _parse_semicolon_list


def _sheet_rows(sheets: dict[str, pd.DataFrame], name: str, required: list[str]) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    if name not in sheets:
        errors.append(f"Missing sheet: {name!r}")
        return [], errors

    df = _normalize_columns(sheets[name])
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        errors.append(f"Sheet {name!r} is missing required column(s): {', '.join(missing_cols)}")
        return [], errors

    rows = []
    for i, row in df.iterrows():
        record = {c: row.get(c) for c in df.columns}
        if all(_clean_str(v) == "" for v in record.values()):
            continue  # blank row
        record["_row_number"] = i + 2  # header is row 1, pandas is 0-indexed
        rows.append(record)
    return rows, errors


def parse_workbook(file) -> ParsedWorkbook:
    sheets = pd.read_excel(file, sheet_name=None, dtype=object)

    result = ParsedWorkbook()

    if SHEET_ADMINS in sheets:
        admin_rows, errs = _sheet_rows(sheets, SHEET_ADMINS, ["name"])
        result.sheet_errors += errs
        result.admins = [
            {"row": r["_row_number"], "name": _clean_str(r.get("name")), "email": _clean_str(r.get("email"))}
            for r in admin_rows
        ]

    associate_rows, errs = _sheet_rows(sheets, SHEET_ASSOCIATES, ["name"])
    result.sheet_errors += errs
    result.associates = [
        {
            "row": r["_row_number"],
            "name": _clean_str(r.get("name")),
            "email": _clean_str(r.get("email")),
            "photo_filename": _clean_str(r.get("photo_filename")),
            "bio": _clean_str(r.get("bio")),
            "experience_summary": _clean_str(r.get("experience_summary")),
            "project_highlights": _clean_str(r.get("project_highlights")),
            "skills": _parse_semicolon_list(r.get("skills")),
            "interested_teams": _parse_semicolon_list(r.get("interested_teams")),
            "interested_ccas": _parse_semicolon_list(r.get("interested_ccas")),
        }
        for r in associate_rows
    ]

    manager_rows, errs = _sheet_rows(sheets, SHEET_MANAGERS, ["name"])
    result.sheet_errors += errs
    result.managers = [
        {
            "row": r["_row_number"],
            "name": _clean_str(r.get("name")),
            "email": _clean_str(r.get("email")),
            "function": _clean_str(r.get("function")),
            "team_name": _clean_str(r.get("team_name")),
        }
        for r in manager_rows
    ]

    assignment_rows, errs = _sheet_rows(
        sheets, SHEET_ASSIGNMENTS, ["associate_name", "manager_name", "start_date"]
    )
    result.sheet_errors += errs
    for r in assignment_rows:
        kind_text = _clean_str(r.get("kind")).lower() or "primary"
        try:
            kind = AssignmentKind(kind_text)
        except ValueError:
            result.sheet_errors.append(
                f"Sheet {SHEET_ASSIGNMENTS!r} row {r['_row_number']}: unknown kind {kind_text!r} "
                "(expected primary/secondary/cca)"
            )
            continue
        result.assignments.append(
            {
                "row": r["_row_number"],
                "associate_name": _clean_str(r.get("associate_name")),
                "manager_name": _clean_str(r.get("manager_name")),
                "kind": kind,
                "start_date": _parse_date(r.get("start_date")),
                "end_date": _parse_date(r.get("end_date")),
                "goals": _clean_str(r.get("goals")),
                "criteria": _parse_criteria(r.get("criteria")),
                "status": _clean_str(r.get("status")).lower(),
                "objective_score": _parse_float(r.get("objective_score")),
                "subjective_notes": _clean_str(r.get("subjective_notes")),
            }
        )

    if SHEET_SKILLS in sheets:
        skill_rows, errs = _sheet_rows(sheets, SHEET_SKILLS, ["name"])
        result.sheet_errors += errs
        result.skills = [
            {"row": r["_row_number"], "name": _clean_str(r.get("name")), "description": _clean_str(r.get("description"))}
            for r in skill_rows
        ]

    if SHEET_CCA_ACTIVITIES in sheets:
        cca_rows, errs = _sheet_rows(sheets, SHEET_CCA_ACTIVITIES, ["name", "organizer_name"])
        result.sheet_errors += errs
        for r in cca_rows:
            status_text = _clean_str(r.get("status")).lower() or "open"
            try:
                status = CcaStatus(status_text)
            except ValueError:
                result.sheet_errors.append(
                    f"Sheet {SHEET_CCA_ACTIVITIES!r} row {r['_row_number']}: unknown status "
                    f"{status_text!r} (expected open/closed)"
                )
                continue
            result.cca_activities.append(
                {
                    "row": r["_row_number"],
                    "name": _clean_str(r.get("name")),
                    "organizer_name": _clean_str(r.get("organizer_name")),
                    "organizer_email": _clean_str(r.get("organizer_email")),
                    "status": status,
                }
            )

    return result


@dataclass
class RowResult:
    sheet: str
    row: int | None
    status: str  # "created" | "updated" | "reused" | "skipped" | "error"
    message: str


@dataclass
class ImportResult:
    row_results: list[RowResult] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.row_results:
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts


def _find_or_upsert_party(
    party_repo,
    party_type: str,
    name: str,
    email: str,
    results: list[RowResult],
    row: int,
    extra_attributes: dict[str, Any] | None = None,
) -> Party | None:
    """Match by email first, then by unambiguous exact name (same rule as
    before); a matched Party's `attributes` are upserted to whatever the
    row now says (Phase 5) rather than left untouched. `display_name`
    itself is never changed on a match — `PartyRepo.update_attributes`
    has no port for that; see this module's docstring."""
    if not name:
        results.append(RowResult(party_type, row, "error", "Missing name"))
        return None

    existing = party_repo.list_by_type(party_type)
    match: Party | None = None
    if email:
        match = next((p for p in existing if p.attributes.get("email") == email), None)

    if match is None:
        name_matches = [p for p in existing if p.display_name == name]
        if len(name_matches) > 1 and not email:
            results.append(
                RowResult(
                    party_type, row, "error",
                    f"{name}: multiple existing {party_type}s share this name — add an email to disambiguate",
                )
            )
            return None
        if len(name_matches) == 1:
            match = name_matches[0]

    if match is not None:
        updates = dict(extra_attributes or {})
        if email:
            updates["email"] = email
        updates = {k: v for k, v in updates.items() if v != match.attributes.get(k)}
        if updates:
            match = party_repo.update_attributes(match.id, **updates)
            results.append(RowResult(party_type, row, "updated", f"{name}: updated"))
        else:
            results.append(RowResult(party_type, row, "reused", f"{name}: unchanged"))
        return match

    attributes = dict(extra_attributes or {})
    if email:
        attributes["email"] = email
    party = Party(party_type=party_type, display_name=name, attributes=attributes)
    party_repo.add(party)
    results.append(RowResult(party_type, row, "created", f"{name}: created"))
    return party


def _upsert_skill(catalog_service, skills_by_name: dict[str, Any], name: str, description: str, results, row, sheet=SHEET_SKILLS):
    if not name:
        return None
    existing = skills_by_name.get(name)
    if existing is not None:
        results.append(RowResult(sheet, row, "reused", f"{name}: already in Skills catalog"))
        return existing
    skill = catalog_service.add_skill(name)
    skills_by_name[name] = skill
    results.append(RowResult(sheet, row, "created", f"{name}: added to Skills catalog"))
    return skill


def match_photos_to_associates(
    photos_zip: bytes, associates: list[dict[str, Any]]
) -> dict[str, tuple[str, bytes]]:
    """Maps each Associates-sheet row's key (its `name`, used only as a
    dict key here) to (source filename, image bytes) by matching a
    zip entry's filename (stem, case-insensitive) against either the
    row's `email` or its `photo_filename` column — per spec: "named to
    match their email or the `photo_filename` column." `photo_filename`
    is checked as a whole-filename match first (it may already include an
    extension), falling back to a stem-only match against either column
    so `casey@example.com.jpg` or `casey.jpg` both work."""
    matches: dict[str, tuple[str, bytes]] = {}
    with zipfile.ZipFile(io.BytesIO(photos_zip)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            entry_name = info.filename.rsplit("/", 1)[-1]
            stem = entry_name.rsplit(".", 1)[0].lower()
            for row in associates:
                candidates = {c.lower() for c in (row.get("email"), row.get("photo_filename")) if c}
                stems = {c.rsplit(".", 1)[0] for c in candidates}
                if entry_name.lower() in candidates or stem in stems:
                    matches[row["name"]] = (entry_name, zf.read(info))
                    break
    return matches


def apply_import(
    services, parsed: ParsedWorkbook, photos_zip: bytes | None = None
) -> ImportResult:
    results: list[RowResult] = []

    for a in parsed.admins:
        _find_or_upsert_party(
            services.party_repo, "functional_owner", a["name"], a["email"], results, a["row"]
        )
    for a in parsed.associates:
        _find_or_upsert_party(services.party_repo, "agent", a["name"], a["email"], results, a["row"])
    for m in parsed.managers:
        extra = {"function": m["function"]} if m.get("function") else None
        _find_or_upsert_party(
            services.party_repo, "manager", m["name"], m["email"], results, m["row"], extra
        )

    associates_by_name = {p.display_name: p for p in services.party_repo.list_by_type("agent")}
    managers_by_name = {p.display_name: p for p in services.party_repo.list_by_type("manager")}

    # -- Skills catalog (renamed from "Criteria Library" — now feeds the
    # live catalog rather than sitting as reference-only, per Phase 5). --
    skills_by_name = {s.name: s for s in services.catalog_service.list_skills()}
    for row in parsed.skills:
        _upsert_skill(services.catalog_service, skills_by_name, row["name"], row["description"], results, row["row"])

    # -- Teams catalog, seeded off Managers.team_name (Phase 5, new). --
    teams_by_name = {t.name: t for t in services.catalog_service.list_teams()}
    for m in parsed.managers:
        team_name = m.get("team_name")
        manager = managers_by_name.get(m["name"])
        if not team_name or manager is None:
            continue
        existing_team = teams_by_name.get(team_name)
        if existing_team is not None:
            if existing_team.manager_id != manager.id:
                results.append(
                    RowResult(
                        SHEET_MANAGERS, m["row"], "error",
                        f"Team {team_name!r} already belongs to a different manager",
                    )
                )
            else:
                results.append(RowResult(SHEET_MANAGERS, m["row"], "reused", f"Team {team_name!r}: unchanged"))
            continue
        team = services.catalog_service.add_team(team_name, manager.id)
        teams_by_name[team_name] = team
        results.append(RowResult(SHEET_MANAGERS, m["row"], "created", f"Team {team_name!r}: created"))

    # -- CCA Activities catalog (new sheet, Phase 5). --
    ccas_by_name = {c.name: c for c in services.catalog_service.list_cca_activities()}
    for row in parsed.cca_activities:
        organizer = managers_by_name.get(row["organizer_name"])
        if organizer is None:
            results.append(
                RowResult(SHEET_CCA_ACTIVITIES, row["row"], "error", f"Unknown organizer {row['organizer_name']!r}")
            )
            continue
        existing_cca = ccas_by_name.get(row["name"])
        if existing_cca is not None:
            if existing_cca.organizer_manager_id != organizer.id or existing_cca.status != row["status"]:
                existing_cca.organizer_manager_id = organizer.id
                existing_cca.status = row["status"]
                services.catalog_repo.update_cca_activity(existing_cca)
                results.append(RowResult(SHEET_CCA_ACTIVITIES, row["row"], "updated", f"{row['name']}: updated"))
            else:
                results.append(RowResult(SHEET_CCA_ACTIVITIES, row["row"], "reused", f"{row['name']}: unchanged"))
            continue
        cca = services.catalog_service.add_cca_activity(row["name"], organizer.id)
        if row["status"] != cca.status:
            cca.status = row["status"]
            services.catalog_repo.update_cca_activity(cca)
        ccas_by_name[row["name"]] = cca
        results.append(RowResult(SHEET_CCA_ACTIVITIES, row["row"], "created", f"{row['name']}: created"))

    # -- Photos (optional, matched by email or photo_filename) --
    photo_matches = match_photos_to_associates(photos_zip, parsed.associates) if photos_zip else {}

    # -- Associate profile / skills / interest flags (Phase 5, new). --
    for row in parsed.associates:
        associate = associates_by_name.get(row["name"])
        if associate is None:
            continue  # party-creation error already reported above
        photo_match = photo_matches.get(row["name"])
        if photo_match is not None:
            source_name, data = photo_match
            row = dict(row)
            row["photo_url"] = photo_storage.save_photo(associate.id, source_name, data)
            results.append(RowResult(SHEET_ASSOCIATES, row["row"], "updated", f"{row['name']}: photo saved"))
        _apply_associate_profile(services, associate, row, skills_by_name, teams_by_name, ccas_by_name, results)

    # -- Assignments (open, or already-finished/scored) --
    for row in parsed.assignments:
        _apply_assignment_row(services, associates_by_name, managers_by_name, row, results)

    return ImportResult(row_results=results)


def _apply_associate_profile(services, associate, row, skills_by_name, teams_by_name, ccas_by_name, results) -> None:
    """Upserts the associate's lean profile, self-declared skills, and
    standing interest flags. Judgment call on the two free-text profile
    columns: `experience_summary` becomes a single ExperienceEntry (there
    is no per-entry structure in the sheet, just one summary column), and
    `project_highlights` is split on ';' into one ProjectHighlight per
    entry (closer to how the field is actually used — a short list of
    highlights, not one paragraph)."""
    from catalog.domain import AssociateProfile, ExperienceEntry, ProjectHighlight

    catalog_service = services.catalog_service
    existing_profile = catalog_service.get_profile(associate.id)
    experience = (
        [ExperienceEntry(title="Prior experience", description=row["experience_summary"])]
        if row["experience_summary"]
        else (existing_profile.experience if existing_profile else [])
    )
    highlights = (
        [ProjectHighlight(title=h) for h in _parse_semicolon_list(row["project_highlights"])]
        if row["project_highlights"]
        else (existing_profile.project_highlights if existing_profile else [])
    )
    photo_url = existing_profile.photo_url if existing_profile else None
    if row.get("photo_url"):  # populated by apply_photos_zip before this runs, if provided
        photo_url = row["photo_url"]

    if row["bio"] or row["experience_summary"] or row["project_highlights"] or photo_url != (existing_profile.photo_url if existing_profile else None):
        profile = AssociateProfile(
            agent_id=associate.id,
            bio=row["bio"] or (existing_profile.bio if existing_profile else ""),
            photo_url=photo_url,
            experience=experience,
            project_highlights=highlights,
        )
        catalog_service.update_profile(profile)
        results.append(RowResult(SHEET_ASSOCIATES, row["row"], "updated", f"{row['name']}: profile upserted"))

    skill_names_by_id = {sk.id: sk.name for sk in skills_by_name.values()}
    existing_skill_names = {
        skill_names_by_id[s.skill_id]
        for s in catalog_service.list_associate_skills(associate.id)
        if s.skill_id in skill_names_by_id
    }
    for skill_name in row["skills"]:
        skill = _upsert_skill(catalog_service, skills_by_name, skill_name, "", results, row["row"], sheet=SHEET_ASSOCIATES)
        if skill is not None and skill_name not in existing_skill_names:
            catalog_service.declare_associate_skill(associate.id, skill.id, SkillSource.SELF)
            results.append(RowResult(SHEET_ASSOCIATES, row["row"], "updated", f"{row['name']}: skill {skill_name!r} added"))

    active_flags = catalog_service.list_interests(associate.id)
    flagged_team_ids = {f.target_id for f in active_flags if f.target_type == InterestTargetType.TEAM}
    flagged_cca_ids = {f.target_id for f in active_flags if f.target_type == InterestTargetType.CCA}
    for team_name in row["interested_teams"]:
        team = teams_by_name.get(team_name)
        if team is None:
            results.append(RowResult(SHEET_ASSOCIATES, row["row"], "error", f"Unknown team {team_name!r} in interested_teams"))
            continue
        if team.id not in flagged_team_ids:
            catalog_service.flag_interest(associate.id, InterestTargetType.TEAM, team.id)
            results.append(RowResult(SHEET_ASSOCIATES, row["row"], "updated", f"{row['name']}: interest in team {team_name!r} flagged"))
    for cca_name in row["interested_ccas"]:
        cca = ccas_by_name.get(cca_name)
        if cca is None:
            results.append(RowResult(SHEET_ASSOCIATES, row["row"], "error", f"Unknown CCA {cca_name!r} in interested_ccas"))
            continue
        if cca.id not in flagged_cca_ids:
            catalog_service.flag_interest(associate.id, InterestTargetType.CCA, cca.id)
            results.append(RowResult(SHEET_ASSOCIATES, row["row"], "updated", f"{row['name']}: interest in CCA {cca_name!r} flagged"))


def _find_matching_assignment(assignment_repo, agent_id: UUID, manager_id: UUID, kind: AssignmentKind, start_date: date):
    for a in assignment_repo.list_by_agent(agent_id):
        if a.manager_id == manager_id and a.kind == kind and a.start_date == start_date:
            return a
    return None


def _apply_assignment_row(services, associates_by_name, managers_by_name, row, results: list[RowResult]) -> None:
    """Natural key: associate + manager + kind + start_date. A matched
    stint's end_date/goals/criteria are upserted; a `status=closed` row
    against a still-ACTIVE matched (or brand new) assignment actually
    closes it with historical dates and a real score — never "create open
    then leave it to be closed later." A matched stint that is already
    CLOSED is left alone (ClosureRecord is deliberately append-only, per
    capabilities/assignment's design) unless the new row is identical, in
    which case it's reported as unchanged."""
    associate = associates_by_name.get(row["associate_name"])
    manager = managers_by_name.get(row["manager_name"])
    if associate is None:
        results.append(RowResult(SHEET_ASSIGNMENTS, row["row"], "error", f"Unknown associate {row['associate_name']!r}"))
        return
    if manager is None:
        results.append(RowResult(SHEET_ASSIGNMENTS, row["row"], "error", f"Unknown manager {row['manager_name']!r}"))
        return
    if row["start_date"] is None:
        results.append(RowResult(SHEET_ASSIGNMENTS, row["row"], "error", "Missing or unparsable start_date"))
        return

    assignment_service = services.assignment_service
    matched = _find_matching_assignment(
        services.assignment_repo, associate.id, manager.id, row["kind"], row["start_date"]
    )

    is_new = matched is None
    if is_new:
        try:
            assignment = assignment_service.create_assignment(
                agent_id=associate.id,
                manager_id=manager.id,
                start_date=row["start_date"],
                end_date=row["end_date"],
                kind=row["kind"],
            )
        except DuplicateAssignment:
            results.append(
                RowResult(
                    SHEET_ASSIGNMENTS, row["row"], "error",
                    f"{row['associate_name']} already has a different active assignment with {row['manager_name']}",
                )
            )
            return
        except ValueError as e:
            results.append(RowResult(SHEET_ASSIGNMENTS, row["row"], "error", str(e)))
            return
        changed = True
        message = f"{row['associate_name']} -> {row['manager_name']}"
    else:
        assignment = matched
        changed = False
        message = f"{row['associate_name']}: unchanged"
        if assignment.state.value == "active" and assignment.end_date != row["end_date"]:
            assignment.end_date = row["end_date"]
            services.assignment_repo.update(assignment)
            changed = True
            message = f"{row['associate_name']}: end date updated"

    if row["goals"] or row["criteria"]:
        if assignment.state.value == "active":
            try:
                assignment_service.record_goal_setting(
                    assignment.id, row["goals"] or "(imported, no description)", criteria=row["criteria"]
                )
                changed = True
            except GoalSettingFrozen:
                pass  # frozen goals on a matched row — leave them alone, not a hard failure

    if row["status"] == "closed" and assignment.state.value == "active":
        if row["objective_score"] is None:
            results.append(
                RowResult(SHEET_ASSIGNMENTS, row["row"], "error", "status=closed requires objective_score")
            )
            return
        if row["end_date"] is None:
            results.append(
                RowResult(SHEET_ASSIGNMENTS, row["row"], "error", "status=closed requires end_date")
            )
            return
        try:
            assignment_service.close_assignment(
                assignment.id,
                objective_score=row["objective_score"],
                subjective_notes=row["subjective_notes"],
                reason="completed",
                as_of=row["end_date"],
            )
            changed = True
            message = f"{row['associate_name']}: closed & scored ({row['objective_score']})"
        except Exception as e:  # noqa: BLE001 — a bulk-import row boundary:
            # report whatever `close_assignment` raises as this row's
            # error and move on to the next row, rather than aborting
            # the whole import over one bad row.
            results.append(RowResult(SHEET_ASSIGNMENTS, row["row"], "error", f"Could not close: {e}"))
            return
    elif row["status"] == "closed" and assignment.state.value == "closed":
        closure = services.assignment_repo.get_closure_record(assignment.id)
        if closure is not None and closure.objective_score == row["objective_score"]:
            message = f"{row['associate_name']}: already closed & scored, unchanged"
        else:
            results.append(
                RowResult(
                    SHEET_ASSIGNMENTS, row["row"], "skipped",
                    f"{row['associate_name']}: already closed with a different score — closure records are "
                    "append-only; use the admin Approvals reopen action to correct a score, not re-import",
                )
            )
            return

    if is_new:
        results.append(RowResult(SHEET_ASSIGNMENTS, row["row"], "created", message))
    else:
        results.append(RowResult(SHEET_ASSIGNMENTS, row["row"], "updated" if changed else "reused", message))
