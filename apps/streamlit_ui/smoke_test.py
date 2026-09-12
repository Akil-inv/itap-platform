"""Not a unit test suite (those live in capabilities/*/tests) — a
throwaway script proving the wired-together Streamlit app actually runs
end to end: seed data, view as each of the three roles, exercise the
main actions on each. Delete or replace with a real AppTest suite once
the UI stabilizes.
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./smoke_test.db"

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py")
at.run()
assert not at.exception, f"Initial render raised: {at.exception}"
assert "Seed demo data" in str(at.button[0].label)

at.button[0].click().run()
assert not at.exception, f"Seeding raised: {at.exception}"

# First party in the sidebar selectbox should be the functional owner
select = at.sidebar.selectbox[0]
assert "functional_owner" in select.value or "Functional Owner" in select.value
assert not at.exception

print("Viewing as:", select.value)
assert "Functional Owner" in at.title[0].value

# Switch to viewing as the manager
manager_option = next(o for o in select.options if "manager" in o.lower())
at.sidebar.selectbox[0].set_value(manager_option).run()
assert not at.exception, f"Switching to manager raised: {at.exception}"
assert "Manager:" in at.title[0].value

# Still viewing as the manager: record goal setting through the real form
at.sidebar.selectbox[0].set_value(manager_option).run()
assert not at.exception
goal_text_areas = [w for w in at.text_area if w.label.startswith("Goals")]
assert goal_text_areas, "Expected a goal-setting text area for the manager's assignment"
goal_text_areas[0].set_value("Ship the onboarding module").run()
submit_buttons = [b for b in at.button if b.label == "Record goal setting"]
assert submit_buttons, "Expected a 'Record goal setting' button"
submit_buttons[0].click().run()
assert not at.exception, f"Recording goal setting raised: {at.exception}"

# Switch to viewing as the agent
agent_option = next(o for o in select.options if "agent" in o.lower())
at.sidebar.selectbox[0].set_value(agent_option).run()
assert not at.exception, f"Switching to agent raised: {at.exception}"
assert "Agent:" in at.title[0].value
assert any("Ship the onboarding module" in m.value for m in at.markdown), (
    "Agent should see the goal setting their manager just recorded"
)

print("SMOKE TEST PASSED")
