"""AppTest coverage for the Phase 3 manager screens from
docs/associate_journey_redesign.md's "Manager flow" section: the
Current/Rolled Off My Team list (`views/manager.py`) and the manager's
Associate page (`views/manager_associate.py` — Profile / Goals /
Review & Scoring). Same bare-script-via-AppTest convention as
smoke_test.py / test_admin_journey_ui.py — run directly:

    rm -f test_manager_journey_ui.db && python test_manager_journey_ui.py
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_manager_journey_ui.db"

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

click_button_labeled(at, "Alex")
assert not at.exception, f"Signing in as Alex raised: {at.exception}"
assert "My Team" in at.title[0].value

# --- My Team list: Current / Rolled Off, no score anywhere -------------

tab_labels = [t.label for t in at.tabs]
assert tab_labels == ["Current", "Rolled Off"], tab_labels

assert any(b.label == "Casey" for b in at.button), "Expected Casey (Alex's Primary) in My Team"
all_markdown = "".join(m.value for m in at.markdown)
assert "itap-battery" in all_markdown, "Expected the tenure battery bar to render"
# Hard rule: managers never see any score, not even hidden — no numeric
# score marker, no eye-icon/popover reveal control anywhere on this page.
assert not at.get("popover"), "My Team must carry no score reveal at all, unlike the admin's list"

print("My Team list: OK")

# --- Manager's Associate page: Profile / Goals / Review & Scoring ------

click_button_labeled(at, "Casey")
assert not at.exception, f"Opening Casey's page raised: {at.exception}"
assert at.title[0].value == "Casey"
assert [t.label for t in at.tabs] == ["Profile", "Goals", "Review & Scoring"]

# Profile tab renders read-only (no save/edit form — that's the
# associate's own page, a later phase).
assert not any(b.label == "Save profile" for b in at.button)

# Goals: record + freeze through the real form.
goal_text_areas = [w for w in at.text_area if w.label.startswith("Goals")]
assert goal_text_areas, "Expected the Goals tab's text area"
goal_text_areas[0].set_value("Ship the onboarding module; own the launch").run()
click_button_labeled(at, "Save")
assert not at.exception, f"Saving goals raised: {at.exception}"

# Not frozen yet -> Review & Scoring should refuse to accept a score.
assert any(
    "Agree & Freeze the goals" in i.value for i in at.info
), "Expected Review & Scoring to gate on frozen goals"
assert not any(b.label == "Submit score" for b in at.button)

click_button_labeled(at, "Agree & Freeze")
assert not at.exception, f"Freezing goals raised: {at.exception}"
assert any("frozen" in s.value.lower() for s in at.success), "Expected a frozen confirmation"
# Frozen -> no more editable goal text area, only the disabled admin-reopen stub.
assert not any(w.label.startswith("Goals") for w in at.text_area)
assert any(
    b.label == "Ask admin to reopen (Functional Owner → Approvals)" and b.disabled
    for b in at.button
), "Expected a disabled admin-reopen stub for goals"

print("Goals freeze: OK")

# Review & Scoring: score against the one criterion, submit -> frozen.
score_sliders = [s for s in at.slider if "Communication" not in s.label]  # no criteria given -> "Overall"
overall_slider = [s for s in at.slider if s.label == "Overall"]
assert overall_slider, f"Expected an 'Overall' scoring slider, have {[s.label for s in at.slider]}"
overall_slider[0].set_value(4.5).run()
click_button_labeled(at, "Submit score")
assert not at.exception, f"Submitting the score raised: {at.exception}"
assert any("4.5" in s.value or "4.50" in s.value for s in at.success), (
    "Expected the submitted objective score in a success message"
)
assert any(
    b.label == "Ask admin to reopen (Functional Owner → Approvals)" and b.disabled
    for b in at.button
), "Expected a disabled admin-reopen stub for the score"

print("Review & Scoring submit: OK")

# Request Extension (new, gated — NOT the same as the old direct action).
# The success banner is a one-time flash (per Streamlit's own rerun
# convention, see README.md) that doesn't survive AppTest's automatic
# rerun-to-stability; the durable proof is the PENDING request now
# listed under "Requests on this engagement".
click_button_labeled(at, "Request Extension")
assert not at.exception, f"Requesting extension raised: {at.exception}"
assert any("Extension" in m.value and "Pending" in m.value for m in at.markdown), (
    "Expected the pending Extension request to be listed"
)

print("Request Extension: OK")

# Request Closure (also new/gated).
click_button_labeled(at, "Request Closure")
assert not at.exception, f"Requesting closure raised: {at.exception}"
assert any("Closure" in m.value and "Pending" in m.value for m in at.markdown), (
    "Expected the pending Closure request to be listed"
)

print("Request Closure: OK")

# Withdraw is still the direct, no-approval action -> the assignment
# actually closes immediately (no admin gate, unlike the two requests
# above) — Casey drops out of Alex's active engagements right away, so
# the Goals/Review & Scoring tabs now show the "no active engagement"
# state instead of "Withdrawn" (a one-time flash message, like the
# request confirmations, that doesn't survive AppTest's rerun).
click_button_labeled(at, "Withdraw this engagement")
assert not at.exception, f"Withdrawing raised: {at.exception}"
assert any("closed" in i.value or "No active engagement" in i.value for i in at.info), (
    "Expected the engagement to show as no-longer-active after Withdraw"
)

print("Withdraw (direct): OK")

click_button_labeled(at, "← Back to My Team")
assert not at.exception
assert "My Team" in at.title[0].value

print("ALL MANAGER JOURNEY UI TESTS PASSED")
