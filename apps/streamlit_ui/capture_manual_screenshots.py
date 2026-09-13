"""Captures the screenshots `generate_manual_pdfs.py` embeds in the
downloadable User Manual PDFs — same "drive the running server with
Playwright" convention as screenshot_admin_journey.py and friends.

Run against a server already up with seeded demo data (matching that
convention too, not starting its own):

    rm -f manual_screens.db
    DATABASE_URL=sqlite:///./manual_screens.db python3 -c \
        "import test_fixtures; from services import get_services; \
         test_fixtures.seed_basic_demo(get_services())"
    DATABASE_URL=sqlite:///./manual_screens.db streamlit run app.py \
        --server.headless true --server.port 8592 &
    python3 capture_manual_screenshots.py

Writes PNGs to `_manual_screens/` (gitignored — intermediate output,
not something to commit) for `generate_manual_pdfs.py` to pick up.
"""
import os

from playwright.sync_api import sync_playwright

URL = "http://localhost:8592"
OUT_DIR = os.path.join(os.path.dirname(__file__), "_manual_screens")
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

os.makedirs(OUT_DIR, exist_ok=True)


def shot(page, name):
    page.wait_for_timeout(700)
    page.screenshot(path=f"{OUT_DIR}/{name}.png")


def switch_person(page, name):
    page.get_by_role("button", name="Switch person").click()
    page.wait_for_timeout(1000)
    page.get_by_role("button", name=name, exact=True).click()
    page.wait_for_timeout(1200)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(URL)
    page.wait_for_timeout(1500)

    # ---------------- Admin (Priya) ----------------
    page.get_by_role("button", name="Priya", exact=True).click()
    page.wait_for_timeout(1200)
    shot(page, "admin_overview")

    page.get_by_role("tab", name="Onboard & Assign").click()
    shot(page, "admin_onboard_assign")

    page.get_by_role("tab", name="Bulk Setup").click()
    shot(page, "admin_bulk_setup")

    page.get_by_role("tab", name="Approvals").click()
    shot(page, "admin_approvals")

    page.get_by_role("tab", name="Manager Handoff").click()
    shot(page, "admin_manager_handoff")

    page.get_by_role("tab", name="Associates").click()
    shot(page, "admin_associates")

    # ---------------- Manager (Alex) ----------------
    switch_person(page, "Alex")
    shot(page, "manager_my_team")

    page.get_by_role("button", name="Casey", exact=True).click()
    page.wait_for_timeout(1200)
    shot(page, "manager_associate_profile")

    page.get_by_role("tab", name="Goals").click()
    shot(page, "manager_goals")

    page.get_by_role("tab", name="Review & Scoring").click()
    shot(page, "manager_review_scoring")

    # ---------------- Associate (Casey) ----------------
    page.get_by_role("button", name="← Back to My Team").click()
    page.wait_for_timeout(800)
    switch_person(page, "Casey")
    shot(page, "associate_profile")

    page.get_by_role("tab", name="My Progress").click()
    shot(page, "associate_progress")

    page.get_by_role("tab", name="Current Episode(s)").click()
    shot(page, "associate_current_episode")

    page.get_by_role("tab", name="Leave & Interests").click()
    shot(page, "associate_leave_interests")

    browser.close()

print("done:", sorted(os.listdir(OUT_DIR)))
