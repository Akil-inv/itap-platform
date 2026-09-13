"""AppTest coverage for the Phase 2 admin (Functional Owner) screens from
docs/associate_journey_redesign.md: the Associates list, the Associate
Portfolio page, and the Setup page. Same bare-script-via-AppTest
convention as smoke_test.py (not part of the capabilities/*/pytest
suites) — run directly:

    rm -f test_admin_journey_ui.db && python test_admin_journey_ui.py
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_admin_journey_ui.db"

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

click_button_labeled(at, "Priya")
assert not at.exception, f"Signing in as Priya raised: {at.exception}"
assert "Workforce Overview" in at.title[0].value

# --- Associates list -------------------------------------------------

tab_labels = [t.label for t in at.tabs]
for expected in ("Associates", "Setup"):
    assert expected in tab_labels, f"Expected a {expected!r} tab, have {tab_labels}"

# Casey and Dana (seed data) both show up as clickable name buttons.
assert any(b.label == "Casey" for b in at.button), "Expected Casey in the Associates list"
assert any(b.label == "Dana" for b in at.button), "Expected Dana in the Associates list"

# Status filter chips render (radio widget with the four statuses + All).
status_radios = [r for r in at.radio if r.label == "Status"]
assert status_radios, "Expected a Status filter radio"
assert set(status_radios[0].options) == {
    "All", "Active", "Needs attention", "Available", "Completed",
}

# Hidden score: a single shared reveal toggle, never a popover — every
# row starts on a "score_show_<agent_id>" (closed-eye) button; clicking
# one reveals that row's score as a "score_hide_<agent_id>" button and
# clicking a DIFFERENT row's closed-eye button closes the first one
# (only one row is ever revealed at once).
show_buttons = [b for b in at.button if b.key and b.key.startswith("score_show_")]
assert len(show_buttons) >= 2, f"Expected at least 2 closed-eye buttons, got {len(show_buttons)}"

at = show_buttons[0].click().run()
hide_buttons = [b for b in at.button if b.key and b.key.startswith("score_hide_")]
assert len(hide_buttons) == 1, "Expected exactly one row's score revealed after one click"
assert hide_buttons[0].label == "—" or any(
    ch.isdigit() for ch in hide_buttons[0].label
), "Expected the revealed button's label to be the score (or the no-score dash)"

# Revealing a second row's score closes the first — never two at once.
still_closed = [b for b in at.button if b.key and b.key.startswith("score_show_")]
assert still_closed, "Expected another row still showing its closed-eye button"
at = still_closed[0].click().run()
hide_buttons = [b for b in at.button if b.key and b.key.startswith("score_hide_")]
assert len(hide_buttons) == 1, "Expected the previous row's score to close when a new one opens"

print("Associates list: OK")

# --- Associate Portfolio ----------------------------------------------

click_button_labeled(at, "Casey")
assert not at.exception, f"Opening Casey's portfolio raised: {at.exception}"
assert at.title[0].value == "Casey"

portfolio_tab_labels = [t.label for t in at.tabs]
assert portfolio_tab_labels == ["Profile", "Rotation timeline", "Interest flags", "Actions"]

assert any(b.label == "← Back to Associates" for b in at.button)
assert any(b.label == "Close & advance" for b in at.button)
assert any(b.label == "Add Secondary" for b in at.button)

# Casey's seeded Primary assignment (with Alex) should show up as a
# "N responsibilities" expander in the Rotation timeline tab, and the
# cross-team bifurcation Secondary (Bailey) should be anchored to it.
expander_labels = [e.label for e in at.expander]
assert any("responsibilities" in label for label in expander_labels), (
    f"Expected a responsibilities expander, have {expander_labels}"
)

print("Associate Portfolio: OK")

click_button_labeled(at, "← Back to Associates")
assert not at.exception
assert "Workforce Overview" in at.title[0].value

# --- Setup page ---------------------------------------------------------

# Add a new Skill, Team, and CCA activity through the real forms.
skill_input = next(t for t in at.text_input if t.label == "New skill name")
skill_input.set_value("Public Speaking").run()
click_button_labeled(at, "Add skill")
assert not at.exception, f"Adding a skill raised: {at.exception}"

team_input = next(t for t in at.text_input if t.label == "New team name")
team_input.set_value("Platform Team").run()
click_button_labeled(at, "Add team")
assert not at.exception, f"Adding a team raised: {at.exception}"

cca_input = next(t for t in at.text_input if t.label == "New CCA activity name")
cca_input.set_value("Hackathon 2026").run()
click_button_labeled(at, "Add CCA activity")
assert not at.exception, f"Adding a CCA activity raised: {at.exception}"

all_markdown = "".join(m.value for m in at.markdown)
assert "Public Speaking" in all_markdown
assert "Platform Team" in all_markdown
assert "Hackathon 2026" in all_markdown

print("Setup page: OK")

print("ALL ADMIN JOURNEY UI TESTS PASSED")
