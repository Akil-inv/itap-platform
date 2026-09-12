# ITAP Streamlit UI

The front door over `capabilities/party_identity`, `capabilities/assignment`,
and `capabilities/rbac_scope`. Contains no business logic itself — every
action goes through `AssignmentService` or `ScopedAssignmentQueries`.

## Identity (dev-mode stand-in)

There is no real login yet — real auth (CML SSO passthrough vs. a
dedicated login screen) is an open platform question, see
`docs/architecture.md`. The sidebar "View as" picker selects an existing
Party and derives its `Role` from `party_type`. Replacing this with real
auth only touches `app.py`'s viewer construction — nothing downstream.

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

**Known dependency gotcha:** `st.graphviz_chart` (used in the Functional
Owner's Org Structure tab) needs the `graphviz` *Python package*
installed (it's in `requirements.txt`) even though rendering happens
client-side — without it the chart silently renders as an empty,
zero-size element with no error. Also: DOT node identifiers can't contain
hyphens unless quoted, so UUID-based node ids use `.hex` (no hyphens),
not `str(uuid)`.

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
