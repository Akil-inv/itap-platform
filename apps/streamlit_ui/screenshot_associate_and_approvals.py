"""One-off Playwright verification of the Phase 4 screens: the
associate's own "My Journey" page (all four tabs) and the admin's new
Approvals tab. Same pattern as screenshot_manager_journey.py.
"""
import os

from playwright.sync_api import sync_playwright

URL = "http://localhost:8783"
OUT_DIR = "/tmp/itap_associate_approvals_screens"
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

    # Give Priya some Setup data (Team, CCA) for the associate's interest
    # flagging section to have something to flag.
    page.get_by_role("button", name="Priya", exact=True).click()
    page.wait_for_timeout(1200)
    page.get_by_role("tab", name="Setup", exact=True).click()
    page.wait_for_timeout(600)
    page.get_by_label("New team name").fill("Data Team")
    page.get_by_role("button", name="Add team").click()
    page.wait_for_timeout(800)
    page.get_by_label("New CCA activity name").fill("Hackathon 2026")
    page.get_by_role("button", name="Add CCA activity").click()
    page.wait_for_timeout(800)

    # Freeze goals + submit a score + raise an Extension request as Alex,
    # so the admin Approvals tab has something real to screenshot.
    page.get_by_role("button", name="Switch person").click()
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Alex", exact=True).click()
    page.wait_for_timeout(1200)
    page.get_by_role("button", name="Casey", exact=True).click()
    page.wait_for_timeout(1200)
    page.get_by_role("tab", name="Goals", exact=True).click()
    page.wait_for_timeout(600)
    page.get_by_label("Goals (agreed with the associate)").fill("Ship the onboarding module")
    page.get_by_role("button", name="Agree & Freeze").click()
    page.wait_for_timeout(1000)
    page.get_by_role("tab", name="Review & Scoring").click()
    page.wait_for_timeout(600)
    submit = page.get_by_role("button", name="Submit score")
    if submit.count():
        submit.click()
        page.wait_for_timeout(1000)
    page.get_by_role("button", name="Request Extension").click()
    page.wait_for_timeout(1000)

    # --- Associate's own page: My Journey -----------------------------

    page.get_by_role("button", name="Switch person").click()
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Casey", exact=True).click()
    page.wait_for_timeout(1500)
    page.screenshot(path=f"{OUT_DIR}/1_my_journey_profile.png", full_page=True)

    page.get_by_role("tab", name="My Progress").click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/2_my_journey_progress.png", full_page=True)

    page.get_by_role("tab", name="Current Episode(s)").click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/3_my_journey_episodes.png", full_page=True)

    page.get_by_role("tab", name="Leave & Interests").click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/4_my_journey_leave_interests.png", full_page=True)

    flag_button = page.get_by_role("button", name="Flag interest: Data Team")
    if flag_button.count():
        flag_button.click()
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{OUT_DIR}/5_my_journey_interest_flagged.png", full_page=True)

    # --- Admin Approvals tab -------------------------------------------

    page.get_by_role("button", name="Switch person").click()
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Priya", exact=True).click()
    page.wait_for_timeout(1200)
    page.screenshot(path=f"{OUT_DIR}/6_admin_associates_interest_badge.png", full_page=True)

    page.get_by_role("tab", name="Approvals").click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/7_admin_approvals_pending.png", full_page=True)

    browser.close()

print("Screenshots saved to", OUT_DIR)
