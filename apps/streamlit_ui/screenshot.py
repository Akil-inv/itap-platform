"""One-off visual verification script. Drives the running server with
Playwright and saves screenshots of the new/changed screens from the
"fix everything" gap-closing pass.
"""
import os

from playwright.sync_api import sync_playwright

URL = "http://localhost:8768"
OUT_DIR = "/tmp/itap_screens2"
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

os.makedirs(OUT_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page(viewport={"width": 1400, "height": 1300})
    page.goto(URL)
    page.wait_for_timeout(2000)

    seed_button = page.get_by_role("button", name="Seed demo data")
    if seed_button.count():
        seed_button.click()
        page.wait_for_timeout(1500)

    # Sign in as Priya
    page.get_by_role("button", name="Priya", exact=True).click()
    page.wait_for_timeout(1500)

    page.get_by_role("tab", name="Overdue").click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/1_overdue.png", full_page=True)

    page.get_by_role("tab", name="Manager Handoff").click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/2_manager_handoff.png", full_page=True)

    # Try creating a duplicate assignment. Casey/Alex are the default
    # selectbox values and Casey already has an active assignment with
    # Alex from the seed data, so submitting with no changes reproduces
    # the duplicate-pair case.
    page.get_by_role("tab", name="Onboard & Assign").click()
    page.wait_for_timeout(1000)
    form = page.locator('div[data-testid="stForm"]', has_text="Create Assignment")
    print("Agent default:", form.locator('input[aria-label="Agent"]').input_value())
    print("Manager default:", form.locator('input[aria-label="Manager"]').input_value())
    form.get_by_role("button", name="Create Assignment").click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/3_duplicate_error.png", full_page=True)

    # Switch to Alex (manager) and open Casey's assignment -> Withdraw tab
    page.get_by_role("button", name="Switch person").click()
    page.wait_for_timeout(1000)
    page.get_by_role("button", name="Alex", exact=True).click()
    page.wait_for_timeout(1500)
    page.get_by_role("tab", name="Withdraw").first.click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/4_withdraw_tab.png", full_page=True)

    browser.close()

print("Screenshots saved to", OUT_DIR)
