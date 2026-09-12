"""Not part of capabilities/*/tests (this is app-layer, not domain), and
not part of smoke_test.py (that's UI wiring, this is the parsing/import
logic itself). Run directly: `python test_bulk_import.py`.
"""
import io
import os
from datetime import date

os.environ["DATABASE_URL"] = "sqlite:///./test_bulk_import.db"

import bulk_import
from services import get_services

# --- build_template_workbook + parse_workbook round-trip ---

template_bytes = bulk_import.build_template_workbook()
assert template_bytes, "Template should not be empty"

parsed = bulk_import.parse_workbook(io.BytesIO(template_bytes))
assert not parsed.sheet_errors, f"Template itself should parse cleanly: {parsed.sheet_errors}"
assert len(parsed.agents) == 2, parsed.agents
assert len(parsed.managers) == 2, parsed.managers
assert len(parsed.assignments) == 1, parsed.assignments
assert parsed.assignments[0]["agent_name"] == "Casey"
assert parsed.assignments[0]["manager_name"] == "Alex"
assert parsed.assignments[0]["start_date"] == date(2026, 1, 1)
assert parsed.assignments[0]["criteria"] == ["Communication", "Technical Skill", "Ownership"]
assert len(parsed.criteria_library) == 3
print("Template round-trip: OK")

# --- missing sheet / missing column detection ---

import openpyxl

wb = openpyxl.Workbook()
wb.remove(wb.active)
ws = wb.create_sheet("Agents")
ws.append(["full_name"])  # wrong column name
ws.append(["Casey"])
buf = io.BytesIO()
wb.save(buf)
buf.seek(0)

bad = bulk_import.parse_workbook(buf)
assert any("Managers" in e for e in bad.sheet_errors), bad.sheet_errors
assert any("name" in e for e in bad.sheet_errors), bad.sheet_errors
print("Missing sheet/column detection: OK")

# --- apply_import against a real (in-memory-backed) service layer ---

services = get_services()

result = bulk_import.apply_import(services, parsed)
counts = result.counts()
assert counts.get("created", 0) >= 4, counts  # 2 agents + 2 managers + 1 assignment at minimum
assert not any(r.status == "error" for r in result.row_results), result.row_results

agents = {p.display_name for p in services.party_repo.list_by_type("agent")}
managers = {p.display_name for p in services.party_repo.list_by_type("manager")}
assert agents == {"Casey", "Dana"}
assert managers == {"Alex", "Bailey"}

assignments = services.assignment_repo.list_all()
assert len(assignments) == 1
assignment = assignments[0]
goal_setting = services.assignment_repo.get_goal_setting(assignment.id)
assert goal_setting is not None
assert goal_setting.criteria == ["Communication", "Technical Skill", "Ownership"]
print("apply_import creates agents/managers/assignments + goal setting: OK")

# --- re-running the same import is idempotent-ish: matches by name, skips the duplicate assignment ---

result2 = bulk_import.apply_import(services, parsed)
counts2 = result2.counts()
assert counts2.get("reused", 0) == 4, counts2  # same 4 agents/managers matched, not recreated
assert counts2.get("skipped", 0) == 1, counts2  # duplicate active assignment
agents_after = services.party_repo.list_by_type("agent")
assert len(agents_after) == 2, "Re-import must not create duplicate Agents"
print("Re-import is idempotent for people, skips duplicate assignment: OK")

os.remove("test_bulk_import.db")
print("ALL BULK IMPORT TESTS PASSED")
