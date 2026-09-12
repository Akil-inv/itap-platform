"""Not part of capabilities/*/tests (this is app-layer, not domain), and
not part of smoke_test.py (that's UI wiring, this is the parsing/import
logic itself). Run directly: `python test_bulk_import.py`.
"""
import io
import os
import zipfile
from datetime import date

os.environ["DATABASE_URL"] = "sqlite:///./test_bulk_import.db"
os.environ["PHOTO_STORAGE_DIR"] = "./test_bulk_import_photos"

import bulk_import
from assignment.domain import AssignmentKind
from services import get_services

# --- build_template_workbook + parse_workbook round-trip ---

template_bytes = bulk_import.build_template_workbook()
assert template_bytes, "Template should not be empty"

parsed = bulk_import.parse_workbook(io.BytesIO(template_bytes))
assert not parsed.sheet_errors, f"Template itself should parse cleanly: {parsed.sheet_errors}"
assert len(parsed.admins) == 1, parsed.admins
assert len(parsed.associates) == 2, parsed.associates
assert parsed.associates[0]["name"] == "Casey"
assert parsed.associates[0]["skills"] == ["Python", "SQL"]
assert parsed.associates[0]["interested_teams"] == ["Platform Team"]
assert parsed.associates[0]["interested_ccas"] == ["Hackathon"]
assert len(parsed.managers) == 2, parsed.managers
assert parsed.managers[0]["function"] == "Engineering", parsed.managers
assert parsed.managers[0]["team_name"] == "Platform Team", parsed.managers
assert len(parsed.assignments) == 4, parsed.assignments
assert parsed.assignments[0]["associate_name"] == "Casey"
assert parsed.assignments[0]["manager_name"] == "Alex"
assert parsed.assignments[0]["kind"] == AssignmentKind.PRIMARY
assert parsed.assignments[0]["start_date"] == date(2026, 1, 1)
assert parsed.assignments[0]["criteria"] == ["Communication", "Technical Skill", "Ownership"]
assert parsed.assignments[1]["status"] == "closed"
assert parsed.assignments[1]["objective_score"] == 4.2

# kind=secondary example row: Casey, concurrent with her Primary above,
# under a different manager (Bailey).
secondary_row = parsed.assignments[2]
assert secondary_row["associate_name"] == "Casey"
assert secondary_row["manager_name"] == "Bailey"
assert secondary_row["kind"] == AssignmentKind.SECONDARY
assert secondary_row["start_date"] == date(2026, 2, 1)
assert secondary_row["end_date"] is None

# kind=cca example row: Dana, with "manager_name" naming the CCA's
# organizer/scorer (Alex, who organizes "Hackathon" on the CCA
# Activities sheet) rather than a people-manager relationship.
cca_row = parsed.assignments[3]
assert cca_row["associate_name"] == "Dana"
assert cca_row["manager_name"] == "Alex"
assert cca_row["kind"] == AssignmentKind.CCA
assert cca_row["status"] == "closed"
assert cca_row["objective_score"] == 4.6

assert len(parsed.skills) == 3
assert len(parsed.cca_activities) == 2
assert parsed.cca_activities[0]["status"].value == "open"
assert parsed.cca_activities[1]["status"].value == "closed"
print("Template round-trip: OK")

# --- missing sheet / missing column detection ---

import openpyxl

wb = openpyxl.Workbook()
wb.remove(wb.active)
ws = wb.create_sheet("Associates")
ws.append(["full_name"])  # wrong column name
ws.append(["Casey"])
buf = io.BytesIO()
wb.save(buf)
buf.seek(0)

bad = bulk_import.parse_workbook(buf)
assert any("Managers" in e for e in bad.sheet_errors), bad.sheet_errors
assert any("name" in e for e in bad.sheet_errors), bad.sheet_errors
print("Missing sheet/column detection: OK")

# --- apply_import against a real (SQL-backed) service layer ---

services = get_services()

result = bulk_import.apply_import(services, parsed)
counts = result.counts()
assert not any(r.status == "error" for r in result.row_results), result.row_results
assert counts.get("created", 0) >= 7, counts  # 1 admin + 2 associates + 2 managers + 4 assignments at minimum

admins = {p.display_name for p in services.party_repo.list_by_type("functional_owner")}
agents = {p.display_name for p in services.party_repo.list_by_type("agent")}
managers = {p.display_name for p in services.party_repo.list_by_type("manager")}
assert admins == {"Priya"}
assert agents == {"Casey", "Dana"}
assert managers == {"Alex", "Bailey"}
alex = next(p for p in services.party_repo.list_by_type("manager") if p.display_name == "Alex")
assert alex.attributes.get("function") == "Engineering", alex.attributes

teams = {t.name for t in services.catalog_service.list_teams()}
assert teams == {"Platform Team", "Design Team"}, teams

skills = {s.name for s in services.catalog_service.list_skills()}
assert {"Communication", "Technical Skill", "Ownership", "Python", "SQL"} <= skills, skills

ccas = {c.name for c in services.catalog_service.list_cca_activities()}
assert ccas == {"Hackathon", "Brownbag Series"}, ccas

assignments = services.assignment_repo.list_all()
assert len(assignments) == 4, assignments  # Casey primary+secondary, Dana primary+cca
casey_id = next(p for p in services.party_repo.list_by_type("agent") if p.display_name == "Casey").id
open_assignment = next(a for a in assignments if a.agent_id == casey_id and a.kind == AssignmentKind.PRIMARY)
goal_setting = services.assignment_repo.get_goal_setting(open_assignment.id)
assert goal_setting is not None
assert goal_setting.criteria == ["Communication", "Technical Skill", "Ownership"]

# kind=secondary: Casey's second, concurrent assignment under Bailey.
secondary_assignment = next(a for a in assignments if a.agent_id == casey_id and a.kind == AssignmentKind.SECONDARY)
assert secondary_assignment.state.value == "active"
secondary_manager = next(p for p in services.party_repo.list_by_type("manager") if p.id == secondary_assignment.manager_id)
assert secondary_manager.display_name == "Bailey"
assert len([a for a in assignments if a.agent_id == casey_id]) == 2, (
    "Casey should now have 2 responsibilities: Primary + Secondary"
)

dana = next(p for p in services.party_repo.list_by_type("agent") if p.display_name == "Dana")
dana_assignment = next(a for a in assignments if a.agent_id == dana.id and a.kind == AssignmentKind.PRIMARY)
assert dana_assignment.state.value == "closed", "Historical row with status=closed must be created already-closed"
closure = services.assignment_repo.get_closure_record(dana_assignment.id)
assert closure is not None
assert closure.objective_score == 4.2
assert "ahead of schedule" in closure.subjective_notes

# kind=cca: Dana's CCA episode, organized/scored by Alex, closed & scored.
dana_cca_assignment = next(a for a in assignments if a.agent_id == dana.id and a.kind == AssignmentKind.CCA)
assert dana_cca_assignment.state.value == "closed"
cca_organizer = next(p for p in services.party_repo.list_by_type("manager") if p.id == dana_cca_assignment.manager_id)
assert cca_organizer.display_name == "Alex"
cca_closure = services.assignment_repo.get_closure_record(dana_cca_assignment.id)
assert cca_closure is not None
assert cca_closure.objective_score == 4.6
assert len([a for a in assignments if a.agent_id == dana.id]) == 2, (
    "Dana should now have 2 responsibilities: Primary + CCA"
)
print("apply_import creates agents/managers/teams/skills/ccas/assignments incl. secondary+cca kinds: OK")

# --- associate profile / self-declared skills / interest flags from the template row ---

casey = next(p for p in services.party_repo.list_by_type("agent") if p.display_name == "Casey")
profile = services.catalog_service.get_profile(casey.id)
assert profile is not None
assert "engineer" in profile.bio.lower()
assert len(profile.experience) == 1
assert len(profile.project_highlights) == 2  # "Built the onboarding module; automated ..." split on ';'

casey_skill_names = {
    s.name
    for assoc_skill in services.catalog_service.list_associate_skills(casey.id)
    for s in services.catalog_service.list_skills()
    if s.id == assoc_skill.skill_id
}
assert {"Python", "SQL"} <= casey_skill_names, casey_skill_names

interests = services.catalog_service.list_interests(casey.id)
assert len(interests) == 2  # Data Team + Hackathon
print("Associate profile/skills/interests from Excel: OK")

# --- re-running the SAME import is idempotent: no duplicates, unchanged rows are "reused" ---

result2 = bulk_import.apply_import(services, parsed)
counts2 = result2.counts()
assert not any(r.status == "error" for r in result2.row_results), result2.row_results
assert counts2.get("created", 0) == 0, counts2
agents_after = services.party_repo.list_by_type("agent")
assert len(agents_after) == 2, "Re-import must not create duplicate Associates"
assignments_after = services.assignment_repo.list_all()
assert len(assignments_after) == 4, "Re-import must not create duplicate Assignments"
print("Re-import creates nothing new (idempotent): OK")

# --- Phase 5: re-uploading with ONE changed field is a real UPDATE, not a skip ---

# Change Alex's function and Casey's bio+end date on the still-open assignment.
changed = bulk_import.parse_workbook(io.BytesIO(template_bytes))
for m in changed.managers:
    if m["name"] == "Alex":
        m["function"] = "Platform Engineering"
for a in changed.associates:
    if a["name"] == "Casey":
        a["bio"] = "Now leads the onboarding squad."
for row in changed.assignments:
    if row["associate_name"] == "Casey" and row["kind"] == AssignmentKind.PRIMARY:
        row["end_date"] = date(2026, 12, 31)

result3 = bulk_import.apply_import(services, changed)
counts3 = result3.counts()
assert not any(r.status == "error" for r in result3.row_results), result3.row_results
assert counts3.get("updated", 0) >= 3, counts3  # manager function, profile bio, assignment end_date

alex_after = next(p for p in services.party_repo.list_by_type("manager") if p.display_name == "Alex")
assert alex_after.attributes.get("function") == "Platform Engineering"
casey_profile_after = services.catalog_service.get_profile(casey.id)
assert casey_profile_after.bio == "Now leads the onboarding squad."
casey_assignment_after = next(
    a
    for a in services.assignment_repo.list_all()
    if a.agent_id == casey.id and a.kind == AssignmentKind.PRIMARY and a.state.value == "active"
)
assert casey_assignment_after.end_date == date(2026, 12, 31)

# Still exactly the same number of people/assignments — an update, never a duplicate.
assert len(services.party_repo.list_by_type("manager")) == 2
assert len(services.assignment_repo.list_all()) == 4
print("Re-upload with a changed field UPDATES the matched record, never duplicates: OK")

# --- Phase 5: photos.zip matches by email or photo_filename ---

zip_buf = io.BytesIO()
with zipfile.ZipFile(zip_buf, "w") as zf:
    zf.writestr("casey@example.com.jpg", b"fake-jpeg-bytes")
zip_buf.seek(0)

result4 = bulk_import.apply_import(services, changed, photos_zip=zip_buf.getvalue())
assert not any(r.status == "error" for r in result4.row_results), result4.row_results
casey_profile_with_photo = services.catalog_service.get_profile(casey.id)
assert casey_profile_with_photo.photo_url is not None
assert os.path.exists(casey_profile_with_photo.photo_url)
print("photos.zip matched by email and stored: OK")

os.remove("test_bulk_import.db")
import shutil

shutil.rmtree("test_bulk_import_photos", ignore_errors=True)
print("ALL BULK IMPORT TESTS PASSED")
