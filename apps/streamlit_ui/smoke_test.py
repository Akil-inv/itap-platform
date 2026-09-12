"""Not a unit test suite (those live in capabilities/*/tests) — a
throwaway script proving the wired-together Streamlit app actually runs
end to end: seed data, sign in as each of the three roles via the
landing page, exercise the main actions on each. Delete or replace with
a real AppTest suite once the UI stabilizes.
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./smoke_test.db"

from streamlit.testing.v1 import AppTest

import test_fixtures
from services import get_services


def click_button_labeled(at, label):
    matches = [b for b in at.button if b.label == label]
    assert matches, f"No button labeled {label!r} found. Have: {[b.label for b in at.button]}"
    return matches[0].click().run()


# Phase 5 removed app.py's "Seed demo data" button — seed the same
# fixture directly via the service layer instead of clicking a UI button
# that no longer exists (see test_fixtures.py's docstring).
test_fixtures.seed_basic_demo(get_services())

at = AppTest.from_file("app.py", default_timeout=15)
at.run()
assert not at.exception, f"Initial render raised: {at.exception}"

# No viewer chosen yet -> the landing/sign-in page renders
assert "ITAP" in "".join(m.value for m in at.markdown)
assert any("Priya" == b.label for b in at.button), "Expected a sign-in button for Priya"

click_button_labeled(at, "Priya")
assert not at.exception, f"Signing in as Priya raised: {at.exception}"
assert "Workforce Overview" in at.title[0].value

# Org Structure tab content renders regardless of which tab is visually
# selected (Streamlit runs the whole script every time; tabs are a
# display-time grouping). Casey is seeded with two concurrent managers
# (Alex, Bailey) — the bifurcation callout should name her.
assert any("Casey" in i.value and "more than one manager" in i.value for i in at.info), (
    "Expected a bifurcation callout naming Casey"
)

# Overdue tab: both subsections render (all content renders regardless
# of which tab is visually selected)
subheaders = [s.value for s in at.subheader]
assert "Overdue goal setting" in subheaders
assert "Overdue closure" in subheaders

# Manager Handoff tab: the reassignment form exists (Alex and Bailey
# both exist in the seed data)
assert any(b.label == "Reassign their whole team" for b in at.button)

# Switch person -> sign in as the manager, Alex
click_button_labeled(at, "Switch person")
assert not at.exception
click_button_labeled(at, "Alex")
assert not at.exception, f"Signing in as Alex raised: {at.exception}"
assert "My Team" in at.title[0].value

# Phase 3: "My Team" is a Current/Rolled Off list — drill into Casey's
# page (views/manager_associate.py) to record goal setting through the
# real Goals tab form.
click_button_labeled(at, "Casey")
assert not at.exception, f"Opening Casey's page raised: {at.exception}"
assert at.title[0].value == "Casey"
assert [t.label for t in at.tabs] == ["Profile", "Goals", "Review & Scoring"]

goal_text_areas = [w for w in at.text_area if w.label.startswith("Goals")]
assert goal_text_areas, "Expected a goal-setting text area for the manager's engagement"
goal_text_areas[0].set_value("Ship the onboarding module").run()
click_button_labeled(at, "Save")
assert not at.exception, f"Recording goal setting raised: {at.exception}"

# The Manager-facing "Swap to new manager" primitive was removed per the
# product/spec ownership fix (central team reassigns, not the manager
# unilaterally) — replaced by "Withdraw" for early exits.
assert not any("Swap" in (b.label or "") for b in at.button)
assert any(b.label == "Withdraw this engagement" for b in at.button)

click_button_labeled(at, "← Back to My Team")
assert not at.exception
assert "My Team" in at.title[0].value

# Switch person -> sign in as the agent, Casey
click_button_labeled(at, "Switch person")
assert not at.exception
click_button_labeled(at, "Casey")
assert not at.exception, f"Signing in as Casey raised: {at.exception}"
assert "My Journey" in at.title[0].value
assert any("Ship the onboarding module" in m.value for m in at.markdown), (
    "Agent should see the goal setting their manager just recorded"
)

print("SMOKE TEST PASSED")
