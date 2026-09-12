"""Bulk baseline setup from an Excel workbook: Admins, Associates,
Managers, Assignments (with optional goals + scoring criteria), and a
Criteria Library reference sheet.

Deliberately app-layer, not domain: parsing spreadsheets isn't a
capability concern. This module's job ends at calling AssignmentService/
PartyRepo — same calls the UI forms already make, just driven by rows
instead of a single submit.

Import is a two-phase preview/confirm flow (`parse_workbook` then
`apply_import`), not "upload and immediately mutate the database" —
a bad file should never be able to silently create garbage.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font
from party_identity.domain import Party

from assignment.domain import DuplicateAssignment

SHEET_ADMINS = "Admins"
SHEET_ASSOCIATES = "Associates"
SHEET_MANAGERS = "Managers"
SHEET_ASSIGNMENTS = "Assignments"
SHEET_CRITERIA_LIBRARY = "Criteria Library"

ADMIN_COLUMNS = ["name", "email"]
ASSOCIATE_COLUMNS = ["name", "email"]
# "function" is optional (e.g. "Engineering", "Design") — a grouping label
# stored on Party.attributes["function"], not a separate concept the
# rest of the app enforces or reads yet.
MANAGER_COLUMNS = ["name", "email", "function"]
ASSIGNMENT_COLUMNS = [
    "associate_name",
    "manager_name",
    "start_date",
    "end_date",
    "goals",
    "criteria",
]
CRITERIA_LIBRARY_COLUMNS = ["name", "description"]

_EXAMPLE_ROWS = {
    SHEET_ADMINS: [["Priya", "priya@example.com"]],
    SHEET_ASSOCIATES: [["Casey", "casey@example.com"], ["Dana", ""]],
    SHEET_MANAGERS: [["Alex", "alex@example.com", "Engineering"], ["Bailey", "", "Design"]],
    SHEET_ASSIGNMENTS: [
        [
            "Casey",
            "Alex",
            "2026-01-01",
            "",
            "Ship the onboarding module",
            "Communication; Technical Skill; Ownership",
        ],
    ],
    SHEET_CRITERIA_LIBRARY: [
        ["Communication", "Clarity and frequency of updates to the manager"],
        ["Technical Skill", "Quality and correctness of the work produced"],
        ["Ownership", "Follow-through without needing to be chased"],
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
        SHEET_CRITERIA_LIBRARY: CRITERIA_LIBRARY_COLUMNS,
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
    criteria_library: list[dict[str, Any]] = field(default_factory=list)
    sheet_errors: list[str] = field(default_factory=list)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _clean_str(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _parse_date(value: Any) -> Optional[date]:
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


def _parse_criteria(value: Any) -> list[str]:
    text = _clean_str(value)
    if not text:
        return []
    return [c.strip() for c in text.split(";") if c.strip()]


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
        {"row": r["_row_number"], "name": _clean_str(r.get("name")), "email": _clean_str(r.get("email"))}
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
        }
        for r in manager_rows
    ]

    assignment_rows, errs = _sheet_rows(
        sheets, SHEET_ASSIGNMENTS, ["associate_name", "manager_name", "start_date"]
    )
    result.sheet_errors += errs
    for r in assignment_rows:
        result.assignments.append(
            {
                "row": r["_row_number"],
                "associate_name": _clean_str(r.get("associate_name")),
                "manager_name": _clean_str(r.get("manager_name")),
                "start_date": _parse_date(r.get("start_date")),
                "end_date": _parse_date(r.get("end_date")),
                "goals": _clean_str(r.get("goals")),
                "criteria": _parse_criteria(r.get("criteria")),
            }
        )

    if SHEET_CRITERIA_LIBRARY in sheets:
        lib_rows, errs = _sheet_rows(sheets, SHEET_CRITERIA_LIBRARY, ["name"])
        result.sheet_errors += errs
        result.criteria_library = [
            {"row": r["_row_number"], "name": _clean_str(r.get("name")), "description": _clean_str(r.get("description"))}
            for r in lib_rows
        ]

    return result


@dataclass
class RowResult:
    sheet: str
    row: Optional[int]
    status: str  # "created" | "reused" | "skipped" | "error"
    message: str


@dataclass
class ImportResult:
    row_results: list[RowResult] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.row_results:
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts


def _find_or_create_party(
    party_repo,
    party_type: str,
    name: str,
    email: str,
    results: list[RowResult],
    row: int,
    extra_attributes: Optional[dict[str, Any]] = None,
) -> Optional[Party]:
    if not name:
        results.append(RowResult(party_type, row, "error", "Missing name"))
        return None

    existing = party_repo.list_by_type(party_type)
    if email:
        match = next((p for p in existing if p.attributes.get("email") == email), None)
        if match:
            results.append(RowResult(party_type, row, "reused", f"{name}: matched existing by email"))
            return match

    name_matches = [p for p in existing if p.display_name == name]
    if len(name_matches) == 1 and not email:
        results.append(RowResult(party_type, row, "reused", f"{name}: matched existing by name"))
        return name_matches[0]
    if len(name_matches) > 1:
        results.append(
            RowResult(
                party_type, row, "error",
                f"{name}: multiple existing {party_type}s share this name — add an email to disambiguate",
            )
        )
        return None

    attributes = dict(extra_attributes or {})
    if email:
        attributes["email"] = email
    party = Party(party_type=party_type, display_name=name, attributes=attributes)
    party_repo.add(party)
    results.append(RowResult(party_type, row, "created", f"{name}: created"))
    return party


def apply_import(services, parsed: ParsedWorkbook) -> ImportResult:
    results: list[RowResult] = []

    for a in parsed.admins:
        _find_or_create_party(
            services.party_repo, "functional_owner", a["name"], a["email"], results, a["row"]
        )
    for a in parsed.associates:
        _find_or_create_party(services.party_repo, "agent", a["name"], a["email"], results, a["row"])
    for m in parsed.managers:
        extra = {"function": m["function"]} if m.get("function") else None
        _find_or_create_party(
            services.party_repo, "manager", m["name"], m["email"], results, m["row"], extra
        )

    associates_by_name = {p.display_name: p for p in services.party_repo.list_by_type("agent")}
    managers_by_name = {p.display_name: p for p in services.party_repo.list_by_type("manager")}

    for row in parsed.assignments:
        associate = associates_by_name.get(row["associate_name"])
        manager = managers_by_name.get(row["manager_name"])
        if associate is None:
            results.append(RowResult(SHEET_ASSIGNMENTS, row["row"], "error", f"Unknown associate {row['associate_name']!r}"))
            continue
        if manager is None:
            results.append(RowResult(SHEET_ASSIGNMENTS, row["row"], "error", f"Unknown manager {row['manager_name']!r}"))
            continue
        if row["start_date"] is None:
            results.append(RowResult(SHEET_ASSIGNMENTS, row["row"], "error", "Missing or unparsable start_date"))
            continue

        try:
            assignment = services.assignment_service.create_assignment(
                agent_id=associate.id,
                manager_id=manager.id,
                start_date=row["start_date"],
                end_date=row["end_date"],
            )
        except DuplicateAssignment:
            results.append(
                RowResult(
                    SHEET_ASSIGNMENTS, row["row"], "skipped",
                    f"{row['associate_name']} already has an active assignment with {row['manager_name']}",
                )
            )
            continue
        except ValueError as e:
            results.append(RowResult(SHEET_ASSIGNMENTS, row["row"], "error", str(e)))
            continue

        results.append(
            RowResult(
                SHEET_ASSIGNMENTS, row["row"], "created",
                f"{row['associate_name']} -> {row['manager_name']}",
            )
        )
        if row["goals"] or row["criteria"]:
            services.assignment_service.record_goal_setting(
                assignment.id, row["goals"] or "(imported, no description)", criteria=row["criteria"]
            )

    return ImportResult(row_results=results)
