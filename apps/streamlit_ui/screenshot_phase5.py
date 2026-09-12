"""Playwright visual verification for Phase 5 (client deployment & setup
data model) — same convention as screenshot_admin_journey.py /
screenshot_manager_journey.py / screenshot_associate_and_approvals.py.
Not part of any test suite. Run against a live `streamlit run app.py`
server on :8765 with an EMPTY database:

    rm -f itap.db && rm -rf uploaded_photos
    streamlit run app.py --server.headless true --server.port 8765 &
    python screenshot_phase5.py   # saves PNGs to /tmp/itap_phase5_screens

Walks: the empty-deployment welcome screen (no "Seed demo data" button,
a "Download demo dataset" button instead), creating the first Admin,
the Bulk Setup tab (workbook + photos.zip uploaders, the upload audit
log), uploading + confirming the generated demo workbook, and the
Associates list showing real multi-segment tenure battery bars from a
full year of historical rotation history.
"""
import os

from playwright.sync_api import sync_playwright

OUT = "/tmp/itap_phase5_screens"
os.makedirs(OUT, exist_ok=True)
BASE = "http://localhost:8765"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.goto(BASE)
    page.wait_for_timeout(2500)
    page.screenshot(path=f"{OUT}/01_welcome_no_seed_button.png", full_page=True)

    with page.expect_download() as dl_info:
        page.get_by_text("Download demo dataset (.xlsx)").click()
    demo_path = f"{OUT}/itap_demo_dataset.xlsx"
    dl_info.value.save_as(demo_path)

    page.get_by_text("Add a new person (ITAP Admin setup)").click()
    page.wait_for_timeout(300)
    page.get_by_label("Admin name").fill("Priya")
    page.get_by_text("Create ITAP Admin").click()
    page.wait_for_timeout(1500)

    page.get_by_role("button", name="Priya", exact=True).click()
    page.wait_for_timeout(1200)
    page.screenshot(path=f"{OUT}/03_signed_in_workforce_overview.png", full_page=True)

    page.get_by_role("tab", name="Bulk Setup").click()
    page.wait_for_timeout(800)
    page.screenshot(path=f"{OUT}/04_bulk_setup_tab.png", full_page=True)

    file_input = page.locator('input[type="file"]').first
    file_input.set_input_files(demo_path)
    page.wait_for_timeout(2500)
    page.screenshot(path=f"{OUT}/05_bulk_setup_preview.png", full_page=True)

    page.get_by_text("Confirm and import", exact=True).click()
    page.wait_for_timeout(3000)

    page.get_by_role("tab", name="Associates").click()
    page.wait_for_timeout(1200)
    page.screenshot(path=f"{OUT}/07_associates_list_full_year_battery.png", full_page=True)

    page.get_by_role("tab", name="Bulk Setup").click()
    page.wait_for_timeout(800)
    page.get_by_text("Past uploads (audit log)").click()
    page.wait_for_timeout(500)
    page.screenshot(path=f"{OUT}/08_upload_audit_log.png", full_page=True)

    browser.close()

print("Screenshots saved to", OUT)
