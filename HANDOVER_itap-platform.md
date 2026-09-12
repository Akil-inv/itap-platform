# ITAP-platform

## Project Identity

Created: 2026-09-11
Preferred coding agent: claude-cowork
Project type: python, streamlit
Project root: `/Users/akilanlingam/Projects/AutoScaffold/active/itap-platform`

## Initial Intent


We are building an application, which will help organize the newly recruited workforce into training and transition on the job, they are managed by a central team and get stationed with Line different managers to work and get trained in various job skills. They will be measured by the respective manager on their skills, and certain pre agreed tasks. The tool should allow onboarding on resources by the central team, then the central team assigns the members to different managers or functions, with a start and end date , where the end date is editable by the central team upon request by the manager, meaning the resources gets extended into the same team for let us say 1 more Quarter, and every resources enters the Managers team via a goal setting exercise and exits the team with feedback agains the task some objective and some subjective assessment, and the individual is also able to give a feedback about the managers they worked with, once they complete a tenure the central team can swap them over the other possible teams. we need to build a system capable of handling and managing all of these.

### Primary Objective

Use the initial intent above; clarify ambiguous requirements before expanding scope.

### Initial Scope

Not separately specified. Establish the smallest coherent build slice from the initial intent.

### Explicitly Out of Scope

Not yet specified.

## Mandatory Development Instructions

Before significant architectural or implementation changes, read all selected frameworks:

No frameworks selected. Confirm applicable standards before substantial implementation.

These project-local copies preserve the standards selected at creation.
Identify conflicts explicitly and favor actual project requirements over generic guidance,
while resolving mandatory safety, reliability, or architectural constraints.

## File and Download Rules

All project-associated files must ultimately live inside `/Users/akilanlingam/Projects/AutoScaffold/active/itap-platform`.

### Project Inputs

Place incoming material under `./inputs/`, using:

- `./inputs/documents/`
- `./inputs/data/`
- `./inputs/images/`
- `./inputs/screenshots/`
- `./inputs/other/`

### Browser or Manual Downloads

Browsers may initially save files in `~/Downloads`.
For files belonging to this project:

1. Move or copy the file into the appropriate `./inputs/` category.
2. Verify the project-local copy is valid and accessible.
3. Use the project-local copy for subsequent work.
4. Remove the original project-related copy from `~/Downloads` after verification.
5. Never treat `~/Downloads` as permanent project storage.

### Generated Outputs

Deliverables belong under `./artifacts/`, including PDFs, presentations,
spreadsheets, generated images, exports, and packaged releases.

### Temporary Work

Use `./workspace/scratch/`. Temporary files must not become project dependencies.

## Instructions for the Coding Agent

Before coding:

1. Read this handover completely.
2. Read every file under Mandatory Development Instructions.
3. Inspect the existing project structure.
4. Inspect `PROJECT.yaml`.
5. Check Git status if the project is version-controlled.
6. Do not create project files outside this root unless explicitly required.
7. Do not create competing project scaffolds.
8. Extend the existing structure before introducing new frameworks.

Establish the objective, current state, important constraints, and immediate build slice.
Continue with the smallest coherent implementation.
Keep Current State below accurate at each coherent handoff; it is not a daily log.
Persist important state in the repository, not solely in an AI conversation.

## Current State

Last updated: 2026-09-11

### Completed

- Project workspace and initial handover created.
- Architecture documented in `docs/architecture.md`: an 8-block capability
  catalog design, with an explicit 2026-09-12 decision to prioritize a
  working ITAP platform over premature genericity (build against ITAP's
  own vocabulary now; extract/generalize only once a second real use case
  needs it).
- `capabilities/party_identity/`: domain model, `PartyRepo` port,
  in-memory + SQL adapters. 13 contract tests passing.
- `capabilities/assignment/`: ITAP's assignment lifecycle — Assignment
  state machine (rule-guarded transitions), GoalSetting, ClosureRecord,
  ReverseFeedback, application service. Covers manager-only extension,
  cross-team bifurcation, 30-day min-elapsed closure gate, swap-to-new-
  manager, and an overdue-goal-setting query. 25 tests passing across
  in-memory + SQL (SQLAlchemy Core) adapters.
- `capabilities/rbac_scope/`: 3-way visibility (Functional Owner /
  Manager / Agent) over Assignment data, computed from relationship
  (manager_id/agent_id match) rather than per-role queries. Child records
  (goal setting, closure, reverse feedback) inherit their Assignment's
  visibility. Includes `consolidated_score` for the Functional Owner's
  per-agent rollup. 11 tests passing.
- `apps/streamlit_ui/`: working, clickable UI over all three roles.
  Functional Owner: all-assignments view, onboard Agent/Manager, create
  Assignment, overdue-goal-setting list, consolidated score per Agent.
  Manager: per-Agent panel with goal setting, extension request, closure
  (score + notes), swap-to-new-manager, and reverse feedback received.
  Agent: their own assignments, goals, score, and a form to give
  feedback about their Manager. Identity is a dev-mode "view as" picker
  (see the app's README). Runs against SQLite by default
  (`DATABASE_URL`), Postgres-ready. Verified with `smoke_test.py`
  (Streamlit `AppTest`, headless) — renders all three roles and exercises
  the goal-setting form live end to end.
- UI polish pass (2026-09-12): `theme.py` (custom CSS, hides Streamlit's
  default chrome) and `journey.py` (a 3-stage stepper — Goal Setting →
  Active → Closed — reading the existing Assignment state, no new states
  added) replace the flat, unordered form dump in Manager/Agent views
  with a visible per-assignment journey.
- Product feedback pass (2026-09-12, same day): three follow-up fixes
  based on user review of the polish pass —
  1. `org_tree.py` replaces the graphviz Manager-Agent diagram with a
     hand-built inline SVG showing the **whole current org**: Functional
     Owner(s) → Managers → Agents, three tiers, rounded cards, smooth
     bezier connectors, hover-to-trace highlighting, zero external/CDN
     dependency (confirmed by uninstalling `graphviz` and re-running the
     smoke test — still passes).
  2. `home.py`: a real landing/sign-in page (grouped by role, one button
     per person) replaces the sidebar "View as" dropdown. Identity now
     lives in `st.session_state`, not sidebar navigation.
  3. Page headings are product/task-oriented ("Workforce Overview", "My
     Team", "My Journey") instead of the role name; the signed-in
     person's name moved to a "Welcome back" subheading and a persistent
     header chip ("ITAP · Signed in as {name} ({role})" + "Switch
     person").

  Verified with real Playwright screenshots throughout (AppTest doesn't
  render CSS/JS, so visual claims need a real browser) — this caught and
  fixed two real bugs: `st.graphviz_chart` needed the `graphviz` Python
  package installed or it silently rendered empty (moot now — replaced
  entirely), and DOT node ids built from UUIDs needed `.hex` (hyphens
  break unquoted DOT identifiers) before being replaced.

### In Progress

- Nothing mid-flight; the party_identity + assignment + rbac_scope +
  Streamlit UI slice (including the journey/theme/org-tree/landing-page
  pass) is complete and demoable.

### Next

- Real notification/reminder dispatch (today only a queryable
  "overdue goal setting" list exists, no delivery mechanism, no UI
  button does anything about it yet).
- Outbox/Event Sync to Iceberg — deferred until the CML platform
  questions below are answered.
- Deploying `apps/streamlit_ui` to CML as an actual CML Application, and
  pointing `DATABASE_URL` at a real Postgres instance there — still
  blocked on the open platform questions below.

### Known Issues

- None yet in code. Three CML platform questions are open and block only
  Phase 2+ (Iceberg sync, Flowable/Drools adapters), not the current
  slice — see "Open platform questions" in `docs/architecture.md`:
  package/runtime install rights, internal pod-to-pod networking, and
  whether Impala/Iceberg must be the live system of record or only the
  governed downstream copy.

### Important Decisions

- The project filesystem and this handover are authoritative.
- Stack: Python + Streamlit, deployed as a CML Application. Postgres is
  the system of record; Iceberg (v2, not Kudu) is the governed downstream
  copy via a transactional outbox pattern, not the live OLTP store.
- Architecture: hexagonal/ports-and-adapters per capability block. No
  domain-specific vocabulary is allowed inside a capability block's core
  code — see `docs/architecture.md` for the full rationale and block map.
