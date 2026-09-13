"""In-app user manual — a "How to use ITAP" reference shown from the
persistent header (see app.py), content-scoped to the signed-in
person's own role (rbac_scope.Role) so an Associate never sees Admin
instructions and vice versa.

Deliberately built into the app rather than linking out to an external
docs site: this deployment already has to run fully air-gapped inside
CML (see offline_deploy/), so an external link would be one more thing
that's unreachable from inside the box. Editing the manual is editing
this file — no separate docs pipeline to keep in sync.

Content is structured data, not raw markdown strings: each role gets a
short **screen tour** (what each tab is, for orientation) followed by
**step-by-step workflows** (what to actually click, in order, to get a
real task done) — a reference alone doesn't tell anyone how to run the
process end to end, which is the actual point of a manual. The same
`MANUAL_BY_ROLE` structure is also read directly by
`generate_manual_pdfs.py`, a dev-only script that renders an
illustrated, downloadable PDF per role (real screenshots of the running
app paired with each workflow), so a step written here shows up
identically in both places — there's exactly one place to keep this
content accurate as the UI changes.

The PDFs themselves are pre-built and checked in under
`assets/manuals/<role value>.pdf` rather than generated at request
time: building one needs reportlab/Pillow/Playwright, none of which
belong in this app's runtime requirements.txt (this deployment has to
install everything from an air-gapped wheelhouse — see
offline_deploy/ — and those are sizeable, dev-only tools). Re-run
`generate_manual_pdfs.py` locally and commit the result whenever this
file's content changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import streamlit as st
from rbac_scope import Role

_MANUALS_DIR = Path(__file__).parent / "assets" / "manuals"


@dataclass
class ScreenTour:
    heading: str
    bullets: list[str]


@dataclass
class Workflow:
    title: str
    steps: list[str]
    note: str | None = None


@dataclass
class RoleManual:
    intro: str
    tour: ScreenTour
    workflows: list[Workflow] = field(default_factory=list)


_FUNCTIONAL_OWNER_MANUAL = RoleManual(
    intro=(
        "As an ITAP Admin you set up the org — people, teams, and "
        "assignments — and keep it running: approvals, handoffs, and "
        "tracking what's overdue."
    ),
    tour=ScreenTour(
        heading="What's in Workforce Overview",
        bullets=[
            "**Associates** — every Associate, one row each: current team, "
            "a tenure bar, a status filter, and a hidden score behind an "
            "eye icon. Click a name to open their full portfolio.",
            "**Org Structure** — the reporting tree of Managers and "
            "Functional Owners.",
            "**Onboard & Assign** — add a new Associate or Manager, then "
            "connect an Associate to a Manager.",
            "**Setup** — one-off configuration: Skills, Teams, CCA "
            "activities.",
            "**Approvals** — act on Manager-raised Extension/Closure "
            "requests, and reopen a frozen Goal Setting or Review Score.",
            "**Rotation Plans** — build and preview a rotation curve "
            "across several Associates at once.",
            "**Bulk Setup** — upload a Setup Workbook (.xlsx) to onboard "
            "many people and assignments in one pass.",
            "**Overdue** — Associates with an overdue goal-setting or "
            "episode closure.",
            "**Manager Handoff** — reassign a departing Manager's whole "
            "team to someone else, in one action.",
            "**Consolidated Scores** — an Associate's rolled-up score "
            "across their closed assignments.",
        ],
    ),
    workflows=[
        Workflow(
            title="Onboard a new hire and assign them to a Manager",
            steps=[
                "Open **Onboard & Assign**.",
                "Under **① Onboard people**, type the person's name (and "
                "email, if you have it) and click **Create Associate** — "
                "or **Create Manager**, if you're adding a manager instead.",
                "Under **② Create an assignment**, pick the Associate and "
                "Manager you just created (or any existing pair), set a "
                "start date, and click **Create Assignment**.",
                "Open **Associates** — the new Associate now shows their "
                "Manager under \"Current team\".",
            ],
            note=(
                "Email is optional today, but it's the field a future SSO "
                "or AD login would match against — worth filling in now."
            ),
        ),
        Workflow(
            title="Bring a whole team in at once with Bulk Setup",
            steps=[
                "Open **Bulk Setup** and click **Download template "
                "(.xlsx)** for a blank workbook in the expected layout — "
                "or use the sign-in page's **Download demo dataset** "
                "first, just to see a filled-in example.",
                "Fill in the workbook: Admins, Managers, Associates, "
                "Assignments, Skills, and CCA Activities each get their "
                "own sheet.",
                "Back in **Bulk Setup**, upload the filled-in workbook "
                "(and a `photos.zip` too, if you have headshots).",
                "Review the row counts and the **Preview parsed rows** "
                "tables — nothing is written yet.",
                "Click **Confirm and import**.",
            ],
            note=(
                "Re-uploading the same workbook later is always safe: "
                "each row is matched by its natural key (email for "
                "people, name for catalogs) and updated in place — "
                "nothing is ever duplicated."
            ),
        ),
        Workflow(
            title="Work the Approvals queue",
            steps=[
                "Open **Approvals**.",
                "Under **Pending requests**, read each Manager's Extension "
                "or Closure request and click **Approve** or **Deny**.",
                "Need to fix a mistake after the fact? Use the "
                "**reopen a frozen Goal Setting or Review Score** section "
                "below the queue — pick the Assignment and reopen either "
                "one.",
            ],
            note=(
                "Approving a Closure request is what actually applies the "
                "assignment's frozen Review Score and closes it out."
            ),
        ),
        Workflow(
            title="Hand off a departing Manager's whole team",
            steps=[
                "Open **Manager Handoff**.",
                "Pick the **Departing manager** and the **New manager for "
                "their team**.",
                "Add a note if useful, then click **Reassign their whole "
                "team**.",
            ],
            note=(
                "This closes every one of the departing Manager's active "
                "Assignments with no score — it's a handoff, not a "
                "performance assessment — and opens a fresh Assignment "
                "under the new Manager for each Associate."
            ),
        ),
    ],
)

_MANAGER_MANUAL = RoleManual(
    intro=(
        "As a Line Manager, My Team is where you track the Associates "
        "tasked to you, agree their goals, and score their episodes once "
        "they're done."
    ),
    tour=ScreenTour(
        heading="What's in My Team",
        bullets=[
            "**Current** tab — every Associate currently tasked to you "
            "(Primary, Secondary, or CCA). Click a name to open their "
            "page.",
            "**Rolled Off** tab — read-only history of Associates who've "
            "since moved to a different manager.",
            "On an Associate's own page: **Profile** (read-only), "
            "**Goals** (set/freeze goal-setting), and **Review & "
            "Scoring** (score a completed episode).",
        ],
    ),
    workflows=[
        Workflow(
            title="Agree and freeze an Associate's goals",
            steps=[
                "On **My Team → Current**, click the Associate's name.",
                "Open the **Goals** tab.",
                "Type or edit the agreed goal-setting text.",
                "Once you and the Associate agree, click **Agree & "
                "Freeze**.",
            ],
            note=(
                "Freezing locks the text — the Associate can no longer "
                "edit their own copy after this. Only an Admin can reopen "
                "it (via Approvals) if it needs correcting."
            ),
        ),
        Workflow(
            title="Score a finished episode",
            steps=[
                "Open the Associate's page and go to **Review & "
                "Scoring**.",
                "If goals haven't been frozen yet, freeze them on the "
                "**Goals** tab first — there's nothing to score against "
                "until then.",
                "Fill in the review form and click **Submit score**.",
            ],
            note=(
                "A score you give here is visible to you and rolls into "
                "the Associate's own aggregate — it is never shown as a "
                "number to any other Manager."
            ),
        ),
        Workflow(
            title="Request an extension or early closure",
            steps=[
                "Open the Associate's page.",
                "Scroll to **Request Extension or Closure**.",
                "Fill in the relevant form and click **Request "
                "Extension** or **Request Closure**.",
                "Wait for your Admin to act on it in their Approvals "
                "queue — you'll see the request listed under **Requests "
                "on this engagement** until it's resolved.",
            ],
        ),
    ],
)

_AGENT_MANUAL = RoleManual(
    intro=(
        "My Journey is entirely your own — your profile, your progress, "
        "your current episode(s), and your leave/interest signals. No "
        "one else's data lives here, and no one but you sees your own "
        "aggregate score."
    ),
    tour=ScreenTour(
        heading="What's in My Journey",
        bullets=[
            "**Profile** — your bio, photo, experience, project "
            "highlights, and skills.",
            "**My Progress** — your rotation plan preview, your own "
            "aggregate score, and a history of past episode scores.",
            "**Current Episode(s)** — one card per active assignment, "
            "with a journey stepper and your goal-setting text.",
            "**Leave & Interests** — log upcoming leave and flag "
            "interest in a Team or CCA.",
        ],
    ),
    workflows=[
        Workflow(
            title="Fill in your profile",
            steps=[
                "Open **Profile**.",
                "Fill in your bio and click **Save profile**.",
                "Open **Add an experience entry** or **Add a project "
                "highlight** to add more, then click **Add**.",
                "Open **Add a skill**, type the skill name, and click "
                "**Add skill**.",
            ],
            note=(
                "A skill you add yourself is always marked self-reported. "
                "Skills tied to a specific engagement are added by your "
                "Manager or Admin, not by you."
            ),
        ),
        Workflow(
            title="Set your goals before your Manager freezes them",
            steps=[
                "Open **Current Episode(s)**.",
                "Find the card for the relevant assignment and edit the "
                "goal-setting text.",
                "Click **Save**.",
            ],
            note=(
                "Once your Manager clicks **Agree & Freeze** on their "
                "side, this text becomes read-only for you."
            ),
        ),
        Workflow(
            title="Log leave or flag interest in a Team/CCA",
            steps=[
                "Open **Leave & Interests**.",
                "Under **Annual leave**, pick your date range and click "
                "**Declare leave**.",
                "Under **Flag interest**, click **Flag interest: "
                "<name>** next to any Team or CCA Activity you'd like to "
                "be considered for — click **Remove interest: <name>** "
                "later if that changes.",
            ],
            note=(
                "Leave needs no approval — it's informational. Flagging "
                "interest is a standing signal to your Manager/Admin, "
                "never a placement request."
            ),
        ),
    ],
)

MANUAL_BY_ROLE: dict[Role, RoleManual] = {
    Role.FUNCTIONAL_OWNER: _FUNCTIONAL_OWNER_MANUAL,
    Role.MANAGER: _MANAGER_MANUAL,
    Role.AGENT: _AGENT_MANUAL,
}


def render(role: Role) -> None:
    """Renders the manual for `role` inside whatever container this is
    called under (a popover, in app.py's header)."""
    manual = MANUAL_BY_ROLE[role]
    st.markdown(manual.intro)

    pdf_path = _MANUALS_DIR / f"{role.value}.pdf"
    if pdf_path.exists():
        st.download_button(
            "Download as PDF",
            data=pdf_path.read_bytes(),
            file_name=f"ITAP_User_Manual_{role.value}.pdf",
            mime="application/pdf",
        )

    st.markdown(f"#### {manual.tour.heading}")
    for bullet in manual.tour.bullets:
        st.markdown(f"- {bullet}")

    if manual.workflows:
        st.markdown("#### Step-by-step: common tasks")
        for workflow in manual.workflows:
            with st.expander(workflow.title):
                for i, step in enumerate(workflow.steps, start=1):
                    st.markdown(f"{i}. {step}")
                if workflow.note:
                    st.caption(workflow.note)
