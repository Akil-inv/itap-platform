"""One-off Playwright verification of the three new Phase 2 admin
screens: Associates list, Associate Portfolio, Setup. Same pattern as
screenshot.py / verify_bulk_upload.py.
"""
import os

from playwright.sync_api import sync_playwright

URL = "http://localhost:8781"
OUT_DIR = "/tmp/itap_admin_journey_screens"
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

    page.get_by_role("button", name="Priya", exact=True).click()
    page.wait_for_timeout(1500)

    page.get_by_role("tab", name="Associates").click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/1_associates_list.png", full_page=True)

    # Reveal the hidden score for the first associate row.
    page.get_by_text("👁").first.click()
    page.wait_for_timeout(700)
    page.screenshot(path=f"{OUT_DIR}/2_associates_list_score_revealed.png", full_page=True)

    # Open Casey's portfolio.
    page.get_by_role("button", name="Casey", exact=True).click()
    page.wait_for_timeout(1500)
    page.screenshot(path=f"{OUT_DIR}/3_portfolio_profile.png", full_page=True)

    page.get_by_role("tab", name="Rotation timeline").click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/4_portfolio_timeline.png", full_page=True)

    page.get_by_role("tab", name="Actions").click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/5_portfolio_actions.png", full_page=True)

    page.get_by_role("button", name="← Back to Associates").click()
    page.wait_for_timeout(1000)

    page.get_by_role("tab", name="Setup", exact=True).click()
    page.wait_for_timeout(1000)
    page.screenshot(path=f"{OUT_DIR}/6_setup.png", full_page=True)

    browser.close()

print("Screenshots saved to", OUT_DIR)
