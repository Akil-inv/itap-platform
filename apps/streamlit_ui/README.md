# ITAP Streamlit UI

The front door over `capabilities/party_identity`, `capabilities/assignment`,
and `capabilities/rbac_scope`. Contains no business logic itself — every
action goes through `AssignmentService` or `ScopedAssignmentQueries`.

## Identity (dev-mode stand-in)

There is no real login yet — real auth (CML SSO passthrough vs. a
dedicated login screen) is an open platform question, see
`docs/architecture.md`. `home.py` is the product's landing/sign-in
screen — the one place a person is chosen (stored in
`st.session_state["viewer_party_id"]`), not a sidebar dropdown that also
drives page titles. Once signed in, a persistent header (`app.py`) shows
"Signed in as {name} ({role})" with a "Switch person" control. Replacing
`home.py`'s button-per-person picker with real auth only touches how
`viewer_party_id` gets set — nothing downstream (services, views, RBAC
enforcement) changes.

Page headings are product/task-oriented ("My Team", "My Journey",
"Workforce Overview"), not the signed-in person's name or role — the
person appears as a "Welcome back" line under the heading, not as the
page's identity.

`ITAP_DEV_MODE` (default `true`) gates the "Switch person" control and
the landing page's picker. Setting it to `false` removes the one-click
"become anyone" affordance — a safety valve for a "production-ish"
deployment before real auth exists, not a real security boundary (the
underlying service calls still have no auth of their own).

Onboarding forms (`home.py`'s setup expander, and the Functional Owner's
"Onboard & Assign") include an optional email field, stored under
`Party.attributes["email"]` — the field a future SSO integration would
match an incoming identity against. Nothing reads it yet.

Every person-picker (sign-in buttons, Agent/Manager dropdowns) runs
through `party_helpers.disambiguate_labels`, which appends a short id
suffix only when two people share a display name — otherwise two Agents
both named "Casey" would be indistinguishable in every selection UI.

## Running locally

```bash
cd apps/streamlit_ui
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -e ../../capabilities/party_identity \
    -e ../../capabilities/assignment -e ../../capabilities/rbac_scope
streamlit run app.py
```

Defaults to a local SQLite file (`itap.db`) via `DATABASE_URL` — set it to
a Postgres URL for real use:

```bash
export DATABASE_URL=postgresql://user:pass@host:5432/itap
```

`MIN_DAYS_BEFORE_CLOSURE` (default 30) controls the assignment closure
gate — see `capabilities/assignment/src/assignment/rules_config.py`.

On first run, with no Parties yet, the app offers a "Seed demo data"
button (1 Functional Owner, 2 Managers, 2 Agents, 3 Assignments — Casey
is deliberately double-booked to Alex and Bailey, to demo cross-team
bifurcation) so there is something to click through immediately.

## Theme and journey (`theme.py`, `journey.py`)

`theme.py` injects CSS (hides Streamlit's default chrome, applies a
card/typography theme) and defines the `.itap-stepper` component styles.
`journey.py` reads an Assignment's existing state (no new states added —
this is a pure presentation-layer read of the State pattern already in
`capabilities/assignment`) and renders it as a 3-stage stepper: Goal
Setting → Active → Closed. Both Manager and Agent per-assignment panels
use this so each assignment reads as a journey rather than a flat pile of
unordered forms.

## Org tree (`org_tree.py`)

The Functional Owner's "Org Structure" tab is a hand-built inline SVG
component (rendered via `st.iframe`), not `st.graphviz_chart` — graphviz's
default output read as a technical diagram, not a product visual, and
this needs zero external/CDN dependency (relevant for CML deployment,
where outbound network access to a JS CDN is one of the open platform
questions). It renders the **whole current org** — Functional Owner(s) ->
Managers -> Agents, three tiers, not just a Manager-Agent pair — using
rounded cards, soft drop shadows, and smooth cubic-bezier connectors.
Hovering a card highlights its connections and dims the rest (plain
inline JS, no library). Shows active assignments only — this is "who
reports to whom right now," not a history view (that's the "All
Assignments" tab). An Agent with concurrent, cross-team assignments gets
more than one incoming edge — it's a graph, not a strict tree, by design.

## Lifecycle beyond normal completion

Besides the "completed" closure path (scored, gated by the minimum
elapsed period and by goal setting existing), two administrative closure
paths exist, neither scored and neither gated by minimum-elapsed or
goal-setting — these are organizational events, not performance
assessments:

- **Withdraw** (Manager's per-assignment "Withdraw" tab) — the Agent
  left the program or this rotation early.
- **Manager Handoff** (Functional Owner's "Manager Handoff" tab,
  central-team-only via RBAC) — a Manager is leaving; every one of their
  active Assignments is closed (`closed_reason="manager_departed"`) and
  a fresh Assignment opens for each Agent under the new Manager in one
  action.

Both record a free-text `closure_note` instead of a `ClosureRecord`.

Note: the earlier Manager-facing "Swap to new manager" (self-service,
scored) was removed — it conflicted with the spec ("central team can
swap them"), letting a Manager unilaterally hand an Agent to whichever
peer they chose. The equivalent normal-rotation flow is now: Manager
closes normally (Close assignment tab, scored) once tenure is complete;
Functional Owner creates the next Assignment via "Onboard & Assign" —
both already-existing primitives, no new code needed for that case.

## Smoke test

`smoke_test.py` is not part of the `pytest` suites under `capabilities/`
— it uses `streamlit.testing.v1.AppTest` to run the wired-together app
headlessly and exercise the goal-setting form end to end (manager records
goals → agent sees them via the RBAC-scoped view). Run it after any change
to `app.py`, `services.py`, or `views/`:

```bash
rm -f smoke_test.db && python smoke_test.py
```

## Visual verification (`screenshot.py`)

Not part of any test suite — a one-off dev tool using Playwright to drive
the running server and save real screenshots, since neither `pytest` nor
`AppTest` renders CSS. Useful after any theme/layout change:

```bash
pip install playwright  # not in requirements.txt — dev-only
streamlit run app.py --server.headless true --server.port 8765 &
python screenshot.py   # saves PNGs to /tmp/itap_screens
```
