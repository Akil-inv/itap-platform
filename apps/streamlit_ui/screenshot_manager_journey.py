"""One-off Playwright verification of the Phase 3 manager screens: My
Team (Current/Rolled Off) and the manager's Associate page (Profile /
Goals / Review & Scoring). Same pattern as screenshot_admin_journey.py.
"""
import os

from playwright.sync_api import sync_playwright

URL = "http://localhost:8782"
OUT_DIR = "/tmp/itap_manager_journey_screens"
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

os.makedirs(OUT_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page(viewport={"width": 1400, "height": 1400})
    page.goto(URL)
    page.wait_for_timeout(2000)

    seed_button = page.get_by_role("button", name="Seed demo data")
    if seed_button.count():
        seed_button.click()
        page.wait_for_timeout(1500)

    page.get_by_role("button", name="Alex", exact=True).click()
    page.wait_for_timeout(1500)
    page.screenshot(path=f"{OUT_DIR}/1_my_team_current.png", full_page=True)

    page.get_by_role("tab", name="Rolled Off").click()
    page.wait_for_timeout(800)
    page.screenshot(path=f"{OUT_DIR}/2_my_team_rolled_off.png", full_page=True)

    page.get_by_role("tab", name="Current").click()
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Casey", exact=True).click()
    page.wait_for_timeout(1500)
    page.screenshot(path=f"{OUT_DIR}/3_associate_profile.png", full_page=True)

    page.get_by_role("tab", name="Goals").click()
    page.wait_for_timeout(800)
    page.screenshot(path=f"{OUT_DIR}/4_goals_before_freeze.png", full_page=True)

    page.get_by_label("Goals (agreed with the associate)").fill(
        "Ship the onboarding module; own the launch end to end"
    )
    page.get_by_role("button", name="Agree & Freeze").click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/5_goals_frozen.png", full_page=True)

    page.get_by_role("tab", name="Review & Scoring").click()
    page.wait_for_timeout(800)
    page.screenshot(path=f"{OUT_DIR}/6_review_scoring_entry.png", full_page=True)

    submit = page.get_by_role("button", name="Submit score")
    if submit.count():
        submit.click()
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{OUT_DIR}/7_review_scoring_frozen.png", full_page=True)

    page.get_by_role("button", name="Request Extension").click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/8_request_extension_pending.png", full_page=True)

    browser.close()

print("Screenshots saved to", OUT_DIR)
