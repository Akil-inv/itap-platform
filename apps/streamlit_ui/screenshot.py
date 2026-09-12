"""One-off visual verification script, not part of the app. Drives the
running Streamlit server with Playwright and saves screenshots of each
role's view for a real look at the theme/journey changes.
"""
import sys
import time

from playwright.sync_api import sync_playwright

URL = "http://localhost:8765"
OUT_DIR = "/tmp/itap_screens"

import os

os.makedirs(OUT_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.goto(URL)
    page.wait_for_timeout(3000)

    # Seed demo data
    seed_button = page.get_by_role("button", name="Seed demo data")
    if seed_button.count():
        seed_button.click()
        page.wait_for_timeout(2000)

    page.screenshot(path=f"{OUT_DIR}/1_functional_owner.png", full_page=True)

    # Click "Org Structure" tab
    org_tab = page.get_by_role("tab", name="Org Structure")
    if org_tab.count():
        org_tab.click()
        page.wait_for_timeout(1500)
        page.screenshot(path=f"{OUT_DIR}/2_org_structure.png", full_page=True)

    # Switch to a manager view via the sidebar selectbox
    select = page.locator('section[data-testid="stSidebar"] [data-baseweb="select"]').first
    select.click()
    page.wait_for_timeout(500)
    page.get_by_text("Alex (manager)", exact=True).click()
    page.wait_for_timeout(2000)
    page.screenshot(path=f"{OUT_DIR}/3_manager.png", full_page=True)

    # Switch to an agent view
    select = page.locator('section[data-testid="stSidebar"] [data-baseweb="select"]').first
    select.click()
    page.wait_for_timeout(500)
    page.get_by_text("Casey (agent)", exact=True).click()
    page.wait_for_timeout(2000)
    page.screenshot(path=f"{OUT_DIR}/4_agent.png", full_page=True)

    browser.close()

print("Screenshots saved to", OUT_DIR)
