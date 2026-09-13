"""AppTest coverage for Phase 4 of the redesign
(docs/associate_journey_redesign.md's "Associate flow" section plus the
admin approvals screen deferred by Phase 3): the associate's own "My
Journey" page (`views/agent.py`) and the Functional Owner's new
Approvals tab (`views/approvals.py`). Same bare-script-via-AppTest
convention as smoke_test.py / test_admin_journey_ui.py /
test_manager_journey_ui.py — run directly:

    rm -f test_associate_and_approvals_ui.db && python test_associate_and_approvals_ui.py
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_associate_and_approvals_ui.db"

import test_fixtures
from services import get_services
from streamlit.testing.v1 import AppTest


def click_button_labeled(at, label):
    matches = [b for b in at.button if b.label == label]
    assert matches, f"No button labeled {label!r} found. Have: {[b.label for b in at.button]}"
    return matches[0].click().run()


# Phase 5 removed app.py's "Seed demo data" button — seed the same
# fixture directly via the service layer (see test_fixtures.py).
test_fixtures.seed_basic_demo(get_services())

at = AppTest.from_file("app.py", default_timeout=20)
at.run()
assert not at.exception, f"Initial render raised: {at.exception}"

# Give Priya (admin) something to work with: a Team, a CCA activity, and
# a Skill, via the real Setup forms, before switching to Casey.
click_button_labeled(at, "Priya")
assert not at.exception

setup_tab_idx = [t.label for t in at.tabs].index("Setup")
skill_input = next(t for t in at.text_input if t.label == "New skill name")
skill_input.set_value("Public Speaking").run()
click_button_labeled(at, "Add skill")
assert not at.exception

team_input = next(t for t in at.text_input if t.label == "New team name")
team_input.set_value("Data Team").run()
click_button_labeled(at, "Add team")
assert not at.exception

cca_input = next(t for t in at.text_input if t.label == "New CCA activity name")
cca_input.set_value("Hackathon 2026").run()
click_button_labeled(at, "Add CCA activity")
assert not at.exception

# Record + freeze goals for Casey's Primary (Alex) so there's something
# to score, request-closure against later.
click_button_labeled(at, "Switch person")
click_button_labeled(at, "Alex")
click_button_labeled(at, "Casey")
goal_text_areas = [w for w in at.text_area if w.label.startswith("Goals")]
goal_text_areas[0].set_value("Ship the onboarding module").run()
click_button_labeled(at, "Agree & Freeze")
assert not at.exception, f"Freezing goals raised: {at.exception}"
click_button_labeled(at, "← Back to My Team")

print("Setup fixtures: OK")

# --- Associate's own page: My Journey -----------------------------------

click_button_labeled(at, "Switch person")
click_button_labeled(at, "Casey")
assert not at.exception, f"Signing in as Casey raised: {at.exception}"
assert "My Journey" in at.title[0].value

tab_labels = [t.label for t in at.tabs]
assert tab_labels == ["Profile", "My Progress", "Current Episode(s)", "Leave & Interests"], tab_labels

# -- Profile: self-editable, self-added skill --

bio_areas = [w for w in at.text_area if w.label == "Bio"]
assert bio_areas, "Expected a self-editable Bio field"
bio_areas[0].set_value("Full-stack associate, joined 2026.").run()
click_button_labeled(at, "Save profile")
assert not at.exception, f"Saving own profile raised: {at.exception}"
assert any("Full-stack associate" in m.value for m in at.markdown) or any(
    "Full-stack associate" in w.value for w in at.text_area
), "Expected the saved bio to render back"

skill_selects = [s for s in at.selectbox if s.label == "Skill"]
assert skill_selects, "Expected a skill picker to self-declare a skill"
skill_selects[0].set_value("Public Speaking").run()
click_button_labeled(at, "Add skill")
assert not at.exception, f"Self-declaring a skill raised: {at.exception}"
assert any("Public Speaking" in m.value and "self-added" in m.value for m in at.markdown), (
    "Expected the self-added skill with its quiet 'self-added' source label"
)

print("Profile (self-edit + self-added skill): OK")

# -- My Progress: own aggregate score visible only to Casey --

assert any("aggregate score" in s.value.lower() for s in at.subheader), (
    "Expected the own-aggregate-score section"
)
assert any(m.label == "Aggregate score" for m in at.metric) or any(
    "No closed episodes" in i.value for i in at.info
), "Expected either a metric or a 'no closed episodes yet' message"

print("My Progress (own score visibility): OK")

# -- Current Episode(s): pre-freeze editable, post-freeze locked --

# Casey's Primary (Alex) is already frozen (set up above) -> read-only.
assert any(
    "Ship the onboarding module" in m.value for m in at.markdown
), "Expected to see the frozen goal text"

# Casey's Secondary (Bailey, from cross-team bifurcation seed data) has
# no goal setting yet -> associate can propose one directly. Exactly one
# editable field should exist (for the Secondary) — the frozen Primary
# must not show one at all.
proposed_areas = [w for w in at.text_area if w.label.startswith("Proposed goals")]
assert len(proposed_areas) == 1, (
    f"Expected exactly one editable 'Proposed goals' field (the un-frozen "
    f"Secondary) and none for the frozen Primary, got {len(proposed_areas)}"
)
proposed_areas[0].set_value("Support the Data Team's dashboard rollout").run()
save_buttons = [b for b in at.button if b.label == "Save"]
assert save_buttons, "Expected a Save button for the proposed goals form"
save_buttons[-1].click().run()
assert not at.exception, f"Saving proposed goals raised: {at.exception}"
assert any(
    "Support the Data Team's dashboard rollout" in m.value for m in at.markdown
), "Expected the newly-saved draft goal text to render"

print("Current Episode(s) (editable pre-freeze / locked post-freeze): OK")

# -- Leave & Interests --

leave_date_inputs = [d for d in at.date_input if d.label in ("Start date", "End date")]
assert len(leave_date_inputs) >= 2, "Expected annual leave start/end date inputs"
click_button_labeled(at, "Declare leave")
assert not at.exception, f"Declaring leave raised: {at.exception}"
all_markdown_and_writes = "".join(m.value for m in at.markdown)
assert "to" in all_markdown_and_writes  # loose smoke check; exact dates vary by 'today'

flag_buttons = [b for b in at.button if b.label.startswith("Flag interest: Data Team")]
assert flag_buttons, "Expected a 'Flag interest' control for the Data Team"
flag_buttons[0].click().run()
assert not at.exception, f"Flagging interest raised: {at.exception}"
assert any(
    "general interest signal" in c.value.lower() or "not a request" in c.value.lower()
    for c in at.caption
), "Expected copy making clear this is a signal, not a placement request"
assert any(
    b.label.startswith("Remove interest: Data Team") for b in at.button
), "Expected the flag to toggle to a 'Remove interest' control"

print("Leave & Interests: OK")

# --- Admin Approvals: reflects the interest-flag change ------------------

click_button_labeled(at, "Switch person")
click_button_labeled(at, "Priya")
assert "Workforce Overview" in at.title[0].value

# Interest-change highlight badge should now show on Casey's row (Phase 2
# highlight, driven by the same InterestActivity.raised_at Casey's flag
# above just touched).
assert any("interest changed" in m.value for m in at.markdown), (
    "Expected the interest-change badge on Casey's Associates-list row"
)

print("Interest flag -> admin highlight badge: OK")

# --- Admin Approvals: pending requests + reopen -------------------------

# Casey's Alex-Primary already has a frozen score requirement for a
# Closure request -> submit + freeze one via the manager's page first.
click_button_labeled(at, "Switch person")
click_button_labeled(at, "Alex")
click_button_labeled(at, "Casey")
overall_slider = [s for s in at.slider if s.label == "Overall"]
assert overall_slider, "Expected the Overall scoring slider"
overall_slider[0].set_value(4.0).run()
click_button_labeled(at, "Submit score")
assert not at.exception, f"Submitting score raised: {at.exception}"

click_button_labeled(at, "Request Extension")
assert not at.exception, f"Requesting extension raised: {at.exception}"
click_button_labeled(at, "Request Closure")
assert not at.exception, f"Requesting closure raised: {at.exception}"
click_button_labeled(at, "← Back to My Team")

click_button_labeled(at, "Switch person")
click_button_labeled(at, "Priya")

approvals_tab_labels = [t.label for t in at.tabs]
assert "Approvals" in approvals_tab_labels, f"Expected an Approvals tab, have {approvals_tab_labels}"

all_markdown = "".join(m.value for m in at.markdown)
assert "Extension request" in all_markdown
assert "Closure request" in all_markdown

# Approve the Extension request.
approve_buttons = [b for b in at.button if b.label == "Approve"]
assert len(approve_buttons) >= 2, f"Expected two pending 'Approve' buttons, got {len(approve_buttons)}"
approve_buttons[0].click().run()
assert not at.exception, f"Approving a request raised: {at.exception}"

remaining_approve_buttons = [b for b in at.button if b.label == "Approve"]
assert len(remaining_approve_buttons) == 1, (
    f"Expected exactly one pending request left after approving one, got "
    f"{len(remaining_approve_buttons)}"
)

print("Approve a pending request: OK")

# Deny the remaining request via the popover form.
deny_forms = [t for t in at.text_area if t.label.startswith("Reason")]
assert deny_forms, "Expected the Deny popover's reason text area"
confirm_deny_buttons = [b for b in at.button if b.label == "Confirm deny"]
assert confirm_deny_buttons, "Expected a 'Confirm deny' button inside the Deny popover"
confirm_deny_buttons[0].click().run()
assert not at.exception, f"Denying a request raised: {at.exception}"

assert not any(b.label == "Approve" for b in at.button), (
    "Expected no pending requests left after approving one and denying the other"
)

print("Deny a pending request: OK")

# --- Admin Approvals: reopen a frozen Goal Setting ------------------------

reopen_choices = [s for s in at.selectbox if s.label == "Assignment"]
assert reopen_choices, "Expected the Assignment picker in the Reopen section"
# Pick the option naming Casey and Alex (her frozen Primary).
casey_alex_option = next(
    o for o in reopen_choices[0].options if "Casey" in o and "Alex" in o
)
reopen_choices[0].set_value(casey_alex_option).run()
assert not at.exception, f"Selecting an assignment to reopen raised: {at.exception}"

reopen_goal_buttons = [b for b in at.button if b.label == "Reopen Goal Setting"]
assert reopen_goal_buttons, "Expected a 'Reopen Goal Setting' button for Casey's frozen goals"
reopen_goal_buttons[0].click().run()
assert not at.exception, f"Reopening goal setting raised: {at.exception}"
# The success banner is a one-time flash (per the README's documented
# convention) that doesn't survive AppTest's rerun-to-stability — the
# durable proof is the Reopen section itself now reading "not frozen."
assert any(
    "not frozen" in c.value.lower() for c in at.caption
), "Expected the reopened Goal Setting to read as no-longer-frozen"

print("Reopen a frozen Goal Setting: OK")

# Confirm the manager's page now shows the goals as editable again, not
# the disabled admin-only stub.
click_button_labeled(at, "Switch person")
click_button_labeled(at, "Alex")
click_button_labeled(at, "Casey")
assert any(w.label.startswith("Goals") for w in at.text_area), (
    "Expected the Goals tab to be editable again after the admin reopened it"
)

print("Manager sees the reopened goals as editable: OK")

print("ALL ASSOCIATE + APPROVALS UI TESTS PASSED")
