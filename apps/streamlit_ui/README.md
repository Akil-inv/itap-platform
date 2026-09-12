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
button (1 Functional Owner, 2 Managers, 2 Agents, 2 Assignments) so there
is something to click through immediately.

## Smoke test

`smoke_test.py` is not part of the `pytest` suites under `capabilities/`
— it uses `streamlit.testing.v1.AppTest` to run the wired-together app
headlessly and exercise the goal-setting form end to end (manager records
goals → agent sees them via the RBAC-scoped view). Run it after any change
to `app.py`, `services.py`, or `views/`:

```bash
rm -f smoke_test.db && python smoke_test.py
```
