"""One-off visual verification script, not part of the app. Drives the
running Streamlit server with Playwright and saves screenshots of the
landing page and each role's dashboard for a real look at the org tree
and journey changes.
"""
import os

from playwright.sync_api import sync_playwright

URL = "http://localhost:8767"
OUT_DIR = "/tmp/itap_screens"
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

os.makedirs(OUT_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page(viewport={"width": 1400, "height": 1100})
    page.goto(URL)
    page.wait_for_timeout(3000)

    seed_button = page.get_by_role("button", name="Seed demo data")
    if seed_button.count():
        seed_button.click()
        page.wait_for_timeout(2000)

    page.screenshot(path=f"{OUT_DIR}/1_landing.png", full_page=True)

    # Sign in as the Functional Owner
    page.get_by_role("button", name="Priya", exact=True).click()
    page.wait_for_timeout(2000)
    page.screenshot(path=f"{OUT_DIR}/2_workforce_overview.png", full_page=True)

    org_tab = page.get_by_role("tab", name="Org Structure")
    if org_tab.count():
        org_tab.click()
        page.wait_for_timeout(2000)
        page.screenshot(path=f"{OUT_DIR}/3_org_tree.png", full_page=True)

    # Switch to Alex (manager)
    page.get_by_role("button", name="Switch person").click()
    page.wait_for_timeout(1500)
    page.get_by_role("button", name="Alex", exact=True).click()
    page.wait_for_timeout(2000)
    page.screenshot(path=f"{OUT_DIR}/4_my_team.png", full_page=True)

    # Switch to Casey (agent)
    page.get_by_role("button", name="Switch person").click()
    page.wait_for_timeout(1500)
    page.get_by_role("button", name="Casey", exact=True).click()
    page.wait_for_timeout(2000)
    page.screenshot(path=f"{OUT_DIR}/5_my_journey.png", full_page=True)

    browser.close()

print("Screenshots saved to", OUT_DIR)
