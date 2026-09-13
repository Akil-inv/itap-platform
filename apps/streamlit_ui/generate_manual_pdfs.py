"""Renders each role's section of user_manual.py as an illustrated,
task-oriented PDF into assets/manuals/<role value>.pdf — the files
user_manual.py's "Download as PDF" button serves. Not part of the
app's runtime: needs reportlab and Pillow (`pip install reportlab
pillow`, neither in requirements.txt — see user_manual.py's docstring
for why) plus screenshots already captured by
capture_manual_screenshots.py into _manual_screens/.

Re-run and commit the output whenever user_manual.py's content changes:

    python3 capture_manual_screenshots.py   # see its own docstring first
    python3 generate_manual_pdfs.py
"""
import os
import re

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import user_manual
from rbac_scope import Role
from role_labels import ROLE_DISPLAY_NAME

HERE = os.path.dirname(__file__)
SCREENS_DIR = os.path.join(HERE, "_manual_screens")
OUT_DIR = os.path.join(HERE, "assets", "manuals")

NAVY = colors.HexColor("#1a1a2e")
BRAND = colors.HexColor("#3949ab")
MUTED = colors.HexColor("#666666")
PALE = colors.HexColor("#f0f2fa")
LINE = colors.HexColor("#dcdfea")

# One representative screenshot per workflow, keyed by role + workflow
# title — chosen to match whichever screen the workflow's steps end up
# on. Keep in sync by hand whenever a workflow title in user_manual.py
# changes or a new one is added.
WORKFLOW_SCREENSHOTS = {
    Role.FUNCTIONAL_OWNER: {
        "Onboard a new hire and assign them to a Manager": "admin_onboard_assign.png",
        "Bring a whole team in at once with Bulk Setup": "admin_bulk_setup.png",
        "Work the Approvals queue": "admin_approvals.png",
        "Hand off a departing Manager's whole team": "admin_manager_handoff.png",
    },
    Role.MANAGER: {
        "Agree and freeze an Associate's goals": "manager_goals.png",
        "Score a finished episode": "manager_review_scoring.png",
        "Request an extension or early closure": "manager_associate_profile.png",
    },
    Role.AGENT: {
        "Fill in your profile": "associate_profile.png",
        "Set your goals before your Manager freezes them": "associate_current_episode.png",
        "Log leave or flag interest in a Team/CCA": "associate_leave_interests.png",
    },
}

TOUR_SCREENSHOTS = {
    Role.FUNCTIONAL_OWNER: "admin_overview.png",
    Role.MANAGER: "manager_my_team.png",
    Role.AGENT: "associate_profile.png",
}

styles = getSampleStyleSheet()

cover_title = ParagraphStyle(
    "CoverTitle", parent=styles["Title"], fontSize=30, textColor=NAVY, spaceAfter=6,
)
cover_role = ParagraphStyle(
    "CoverRole", parent=styles["Normal"], fontSize=18, textColor=BRAND,
    alignment=TA_CENTER, spaceAfter=10,
)
cover_intro = ParagraphStyle(
    "CoverIntro", parent=styles["Normal"], fontSize=12, textColor=colors.black,
    alignment=TA_CENTER, leading=17, spaceAfter=4,
)
section_h = ParagraphStyle(
    "SectionH", parent=styles["Heading1"], fontSize=17, textColor=NAVY, spaceBefore=4, spaceAfter=10,
)
workflow_h = ParagraphStyle(
    "WorkflowH", parent=styles["Heading2"], fontSize=13.5, textColor=colors.white,
    backColor=BRAND, borderPadding=(6, 8, 6, 8), spaceAfter=0, leading=17,
)
bullet_style = ParagraphStyle(
    "Bullet", parent=styles["Normal"], fontSize=10, leading=14.5, spaceAfter=6,
)
step_style = ParagraphStyle(
    "Step", parent=styles["Normal"], fontSize=10.5, leading=15, spaceAfter=7,
)
note_style = ParagraphStyle(
    "Note", parent=styles["Normal"], fontSize=9.5, leading=13.5, textColor=colors.HexColor("#3a3a3a"),
)
caption_style = ParagraphStyle(
    "Caption", parent=styles["Normal"], fontSize=8.5, textColor=MUTED,
    alignment=TA_CENTER, spaceBefore=4,
)


def inline(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def screenshot_flowable(filename: str, max_width=6.4 * inch, max_height=3.6 * inch):
    path = os.path.join(SCREENS_DIR, filename)
    with PILImage.open(path) as im:
        w, h = im.size
    scale = min(max_width / w, max_height / h)
    img = Image(path, width=w * scale, height=h * scale)
    img.hAlign = "CENTER"
    return img


def framed_screenshot(filename: str):
    """A screenshot inside a thin bordered table cell, like a browser
    frame, so it reads as a picture of the app rather than a loose
    image floating in the page."""
    img = screenshot_flowable(filename)
    t = Table([[img]], colWidths=[img.drawWidth + 12])
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, LINE),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    t.hAlign = "CENTER"
    return t


def note_box(text: str):
    t = Table([[Paragraph(inline(text), note_style)]], colWidths=[6.4 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("LINEBEFORE", (0, 0), (0, 0), 3, BRAND),
            ]
        )
    )
    return t


def workflow_banner(title: str):
    t = Table([[Paragraph(inline(title), workflow_h)]], colWidths=[6.4 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BRAND),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return t


def build_cover(role: Role, manual) -> list:
    return [
        Spacer(1, 1.6 * inch),
        Paragraph("ITAP User Manual", cover_title),
        Paragraph(ROLE_DISPLAY_NAME[role], cover_role),
        HRFlowable(width="40%", thickness=1, color=LINE, spaceBefore=6, spaceAfter=18, hAlign="CENTER"),
        Paragraph(inline(manual.intro), cover_intro),
        Spacer(1, 0.5 * inch),
        screenshot_flowable(TOUR_SCREENSHOTS[role], max_width=5.5 * inch, max_height=3.2 * inch),
        PageBreak(),
    ]


def build_tour(manual) -> list:
    story = [Paragraph(manual.tour.heading, section_h)]
    for b in manual.tour.bullets:
        story.append(Paragraph("&bull;&nbsp;&nbsp;" + inline(b), bullet_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.75, color=LINE, spaceAfter=14))
    return story


def build_workflows(role: Role, manual) -> list:
    story = []
    screenshots = WORKFLOW_SCREENSHOTS.get(role, {})
    for index, wf in enumerate(manual.workflows):
        block = []
        if index == 0:
            block.append(Paragraph("Step-by-step: common tasks", section_h))
        block.append(workflow_banner(wf.title))
        block.append(Spacer(1, 8))
        for i, step in enumerate(wf.steps, start=1):
            block.append(Paragraph(f"<b>{i}.</b>&nbsp; {inline(step)}", step_style))
        shot = screenshots.get(wf.title)
        if shot:
            block.append(Spacer(1, 4))
            block.append(framed_screenshot(shot))
            block.append(Paragraph("What this screen looks like", caption_style))
        if wf.note:
            block.append(Spacer(1, 8))
            block.append(note_box(wf.note))
        block.append(Spacer(1, 20))
        story.append(KeepTogether(block))
    return story


def build_pdf(role: Role, out_path: str) -> None:
    manual = user_manual.MANUAL_BY_ROLE[role]
    doc = SimpleDocTemplate(
        out_path,
        pagesize=LETTER,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        title=f"ITAP User Manual — {ROLE_DISPLAY_NAME[role]}",
    )
    story = []
    story += build_cover(role, manual)
    story += build_tour(manual)
    story += build_workflows(role, manual)

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(0.85 * inch, 0.5 * inch, "ITAP User Manual")
        canvas.drawRightString(LETTER[0] - 0.85 * inch, 0.5 * inch, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for role in (Role.FUNCTIONAL_OWNER, Role.MANAGER, Role.AGENT):
        build_pdf(role, os.path.join(OUT_DIR, f"{role.value}.pdf"))
