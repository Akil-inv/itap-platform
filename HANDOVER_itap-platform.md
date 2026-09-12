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
- Scenario-based gap analysis + full fix pass (2026-09-12, same day):
  played every role through every lifecycle scenario, found 18 gaps,
  fixed all of them. See "Resolved via scenario-based gap analysis" in
  `docs/architecture.md` for the full list. Highlights: end_date/score/
  duplicate-assignment validation that didn't exist before; optimistic
  concurrency (`Assignment.version` + `ConcurrentModification`) so two
  concurrent writers can't silently clobber each other; closure now
  actually requires goal setting to exist, matching the UI copy that
  already claimed it did; reverse feedback now gated by the same
  minimum-elapsed period as closure; two new administrative closure
  paths (`withdraw_assignment`, `reassign_all_from_departing_manager`)
  that don't force a fabricated performance score; removed the
  Manager-facing `swap_to_new_manager` entirely — it gave managers
  reassignment authority the spec reserves for the central team;
  duplicate-display-name disambiguation in every person-picker; graceful
  handling of an unrecognized `party_type` instead of a crash;
  `ITAP_DEV_MODE` flag as a safety valve (not a real security boundary)
  on the identity-switching UI. `capabilities/assignment` grew from 25 to
  55 tests, `rbac_scope` from 11 to 13, all passing. Verified with the
  smoke test plus real Playwright screenshots of the duplicate-assignment
  error, the new Withdraw tab, Manager Handoff, and the split
  Overdue-goal-setting/Overdue-closure view.
- Bulk Setup (2026-09-12, same day): `bulk_import.py` + a new
  Functional-Owner-only tab — upload an Excel workbook to create Agents,
  Managers, and Assignments (with optional goals + scoring criteria) in
  one pass, template generated on demand, two-phase parse-then-confirm
  so a bad file can't silently create garbage, idempotent re-upload
  (matches existing people by email/name, skips duplicate assignments).
  Added `GoalSetting.criteria: list[str]` (lightweight rubric checklist,
  closure still records one score) to support it — `capabilities/assignment`
  now at 59 tests. Also fixed a genuine Streamlit bug this surfaced: all
  tabs render in one script pass in a fixed order, so an import in a
  later tab (Bulk Setup) couldn't retroactively update an earlier tab
  (Org Structure) already rendered in the same pass — looked exactly
  like a caching bug (correct after a hard reload, stale in-session)
  until a fresh-vs-reloaded Playwright screenshot comparison proved it
  wasn't. Fixed with `st.rerun()` + a session-state flash message; see
  "Bulk Setup + a real Streamlit ordering bug" in `docs/architecture.md`
  for the convention this sets for any future mutating action. New
  `apps/streamlit_ui/test_bulk_import.py` covers the parsing/import
  logic directly (not just UI wiring via smoke_test.py).
- Self-healing schema migration (2026-09-12, same day): a user's existing
  local `itap.db` (created before `criteria`/`version` existed) hit
  `no such column: goal_settings.criteria`, because `metadata.create_all()`
  only creates missing tables, never missing columns on a table that
  already exists. Fixed with `_ensure_columns()` in
  `capabilities/assignment/src/assignment/adapters/sql.py`: after
  `create_all()`, it diffs the real on-disk table against the ORM
  definition and issues `ALTER TABLE ... ADD COLUMN` for anything
  missing, backfilling `version` to `0` and `criteria` to `[]`. Runs
  automatically on every `create_schema()` call, so an old local database
  self-heals on next app start — no need to delete `itap.db`. Not a real
  migration framework; see "Self-healing additive-column migration" in
  `docs/architecture.md`. Verified against a hand-built pre-`criteria`
  SQLite file; all test suites (85 total across the three capabilities)
  plus `smoke_test.py`/`test_bulk_import.py` still pass.

- Restyled front page (2026-09-12, same day): after a mockup review round
  (a standalone HTML/JS artifact, not committed to this repo, used to try
  a two-step "pick your portal" flow, a single-page pitch-panel-plus-
  sign-in-card layout, an intern "learning curve" journey map, and a
  Rotation Plan concept), the approved front page — one page, a pitch
  panel ("one address, three experiences") next to the real sign-in
  card, grouped by role — replaced the flat person-directory in
  `home.py`. New `role_labels.py` gives each role a product-facing name
  ("ITAP Admin" / "Line Manager" / "Intern / Staff") shared by `home.py`
  and `app.py`'s header chip, so the signed-in person's role reads the
  same everywhere; the underlying `Role` enum values are unchanged. The
  rotation-plan/journey-curve ideas from the mockup are not implemented
  yet — they need real domain modeling (a plan template, per-intern
  enrollment/progress) this pass didn't touch; only the front page shipped.
  Verified with `smoke_test.py` (unchanged pass, since button labels
  didn't change) and Playwright screenshots of the sign-in page and the
  post-sign-in header.
- Rotation Plan (2026-09-12, same day): new capability
  `capabilities/rotation_plan/` — a fixed, named path of stages an Agent
  is enrolled into (`RotationPlan` + `Enrollment`, same hexagonal shape
  as every other block), 49 tests passing across in-memory + SQL
  adapters. `RotationPlanService.progress_value()` computes a fractional
  position along the plan for the "journey curve" UI
  (`apps/streamlit_ui/journey_curve.py`, a Python port of the approved
  mockup's curve, rendered as inline SVG via `st.iframe`). Functional
  Owner gets a new "Rotation Plans" tab (create a plan, enroll an Agent,
  see the whole cohort plotted on one curve, manually advance a stage);
  Agent's "My Journey" shows their own plan curve above their existing
  per-Assignment cards. Manual verification caught a real bug — SQLite
  drops datetime tzinfo on round-trip, so `progress_value()` raised a
  naive/aware `TypeError` — fixed and now covered by parametrizing the
  service tests over both adapters (not just in-memory); see "Rotation
  Plan" in `docs/architecture.md` for the full story. Deliberately not
  yet linked to `assignment`: a plan stage is a label, not a specific
  Manager/Assignment — an admin reading both screens is what connects
  them today.
- Stage-to-Assignment linking (2026-09-12, same day): closed that gap.
  `Enrollment.stage_assignments: dict[int, UUID]` maps a stage index to
  the `assignment.Assignment` id covering it (by id only — `rotation_plan`
  still never imports `assignment`); `enroll()`/`advance_stage()` can link
  in the same call, or an admin links after the fact via
  `RotationPlanService.link_assignment()`. Functional Owner's per-person
  row is now an expander showing who covers the current stage, with a
  selector over that Agent's active Assignments to link one. The Agent's
  own journey curve shows the linked Manager's name under each reached
  stage. `rotation_plan` now at 71 tests. A real layout bug turned up
  during manual (Playwright) verification, not the unit suite: the "you
  are here" marker sitting exactly on a stage node (true at progress 0
  and right after every `advance_stage`) collided with that node's own
  labels once a manager sub-label was actually present — fixed in
  `journey_curve.py` by widening the sub-label offset past the marker's
  halo and flipping "You are here" to the opposite side from the node's
  own labels. See "Linking a stage to its Assignment" in
  `docs/architecture.md`.
- Auto-advance on Assignment closure (2026-09-12, same day): closing an
  Assignment linked to an Enrollment's current stage now advances that
  stage automatically — no admin click needed for the common case. New
  `apps/streamlit_ui/rotation_plan_bridge.py`
  (`advance_linked_stage_if_closed`) is the one place allowed to know
  about both `assignment` and `rotation_plan`; called after all three
  ways an Assignment can close (Manager's normal close, Manager's
  withdrawal, Functional Owner's manager handoff — looping once per
  closed Assignment there). No-op, not an error, when the Assignment
  isn't linked to anything or was already the plan's last stage; any
  internal failure is swallowed so it can never turn a successful
  closure into a visible error. New
  `apps/streamlit_ui/test_rotation_plan_bridge.py` (same bare-script
  convention as `test_bulk_import.py`) covers all three cases. Verified
  end to end with Playwright: linked Casey's stage to her Assignment,
  withdrew it as her Manager, confirmed her own journey curve had
  already moved to the next stage. See "Auto-advancing on Assignment
  closure" in `docs/architecture.md`.
- Auto-creating the next Assignment (2026-09-12, same day): closed the
  remaining manual step. `RotationPlan.default_stage_managers` (stage
  index -> Manager id, same by-id-only shape as
  `Enrollment.stage_assignments`) lets an admin name which Manager
  should cover a given stage; new "Default manager per stage" expander
  per plan in Rotation Plans, new `RotationPlanService.
  set_default_manager()` (and `create_plan(default_stage_managers=...)`).
  Both `RotationPlan` and its table gained a `version` column for
  optimistic concurrency, matching `Enrollment`. When
  `rotation_plan_bridge` advances a stage that has a default Manager, it
  now creates a real Assignment under that Manager and links it in the
  same action — falling back to an unlinked advance on
  `DuplicateAssignment`/`ValueError` (e.g. the Agent already has an
  active Assignment with that Manager) rather than failing outright.
  `rotation_plan` now at 91 tests; `test_rotation_plan_bridge.py` covers
  both the auto-create and the no-default-Manager fallback. Verified end
  to end with Playwright: set Priti as Data Team's default Manager,
  withdrew Casey's Platform-Team Assignment, and confirmed her Rotation
  Plans row read "Covered by Priti" with a brand-new Assignment, with no
  admin action beyond the one-time default-Manager setup. See
  "Auto-creating the next Assignment" in `docs/architecture.md`.

- Front page fidelity fix (2026-09-12, same day): the shipped front page
  had drifted from the approved mockup in ways a side-by-side comparison
  made obvious but a description hadn't — no custom typography was ever
  wired in (the mockup's Libre Franklin/Source Sans 3 pairing via Google
  Fonts), "Line Manager" shipped blue (`#4C78A8`) instead of the
  mockup's teal (`#16707F`), and cards were flat where the mockup used a
  soft shadow + 10-14px radius. Fixed in `theme.py` (fonts + shadow
  applied app-wide, so every bordered container — not just the front
  page — picks it up) and `home.py` (role colors corrected to match the
  mockup's `--admin`/`--manager`/`--intern` tokens exactly: `#333F6B`/
  `#16707F`/`#3F7D57`). Also hid Streamlit's auto-injected "copy anchor
  link" icon (`[data-testid="stHeaderActionElements"]`), which leaked
  onto the raw `<h1>` and never appeared in the mockup. Verified with a
  fresh Playwright screenshot compared directly against the mockup's own
  saved HTML — not just a description of what changed. Known,
  deliberately out-of-scope leftover: `journey.py`'s older per-assignment
  stepper (predates the mockup) still uses blue for "current" state,
  inconsistent with the new teal "current" used everywhere the mockup's
  design applies (journey curve, front page) — not touched here since it
  wasn't part of what was actually agreed to in the mockup review.

- Bulk Setup gained Admins + Manager function (2026-09-12, same day):
  the user wanted a large sample dataset (4 ITAP Admins, 15 Managers
  across 5 functions, 40 associates onboarded in scattered batches, one
  mid-rotation leaver) delivered as an Excel file to review/edit before
  uploading — not seeded directly (an earlier `seed_realistic_dataset.py`
  script was built, then removed per that direction). That surfaced a
  real gap: Bulk Setup had no way to onboard an ITAP Admin at all (only
  Agents/Managers), and Managers had nowhere to record which function
  they belong to. Fixed in `bulk_import.py`: new `Admins` sheet
  (`name`/`email`, imported as `functional_owner` Parties) and a new
  optional `function` column on `Managers` (stored as
  `Party.attributes["function"]`) — both additive, so an older workbook
  without them still imports cleanly. `test_bulk_import.py` updated for
  the new sheet/column and passing. The sample dataset itself was
  generated as a one-off workbook using this same template and handed to
  the user directly, not committed to the repo. `org_tree.py`'s Org
  Structure tab is worth knowing about at that scale — it lays every
  Agent out in one fixed-width row, so ~40 cards overlap/truncate; the
  data itself stays correct (confirmed via All Assignments/Overdue), it's
  just a rendering limit not built for a cohort this size yet.

- Agent → Associate rename (2026-09-12, same day): the user asked for
  the product-facing role name "Agent" to read "Associate" everywhere in
  the UI and the Bulk Setup Excel template. Renamed every user-visible
  string — `role_labels.py`'s `ROLE_DISPLAY_NAME`, `home.py`, `app.py`,
  `views/manager.py`, `views/functional_owner.py` (labels, captions,
  dataframe columns, error/success messages) — plus the Bulk Setup
  template's `Agents` sheet → `Associates` and its `agent_name` column →
  `associate_name` (`bulk_import.py`, `ParsedWorkbook.agents` →
  `.associates`, `test_bulk_import.py` updated to match). Internal
  domain vocabulary is untouched by design, per this repo's
  hexagonal/ports-and-adapters convention (see `docs/architecture.md`):
  `party_type="agent"`, `Assignment.agent_id`,
  `AssignmentRepo.list_by_agent`, the `views/agent.py` module name, and
  the "ITAP" product name/tagline all stay as-is. A case-insensitive
  grep sweep (`grep -rniE "agent|intern"`) caught one miss a
  case-sensitive pass didn't (`manager.py`'s lowercase `"Goals (agreed
  with the agent)"`). Playwright verification surfaced a second-order
  bug: `party_helpers.party_label()` built dropdown labels from the raw
  internal `party_type` string, so "Casey (agent)" kept showing in every
  person-picker even after the display strings were renamed — fixed by
  having it look up `ROLE_DISPLAY_NAME[Role(party.party_type)]` instead,
  with a fallback to the raw string. Re-verified via a fresh screenshot
  showing "Casey (Associate)". The sample dataset workbook handed to the
  user earlier used the old `Agents`/`agent_name` schema and was
  regenerated and re-sent under the new `Associates`/`associate_name`
  schema so it still imports cleanly. `smoke_test.py`,
  `test_bulk_import.py`, and `test_rotation_plan_bridge.py` all pass.

### In Progress

- Nothing mid-flight; the party_identity + assignment + rbac_scope +
  Streamlit UI slice (including the journey/theme/org-tree/landing-page
  pass, the scenario-based gap-fix pass, and Bulk Setup) is complete and
  demoable.

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

- `attributes["email"]` is a convention, not an enforced/validated
  schema field — fine for now, worth revisiting when real auth needs
  something to map against.
- `ITAP_DEV_MODE=false` hides the "Switch person" UI but doesn't add
  real authorization to the underlying service calls — not a substitute
  for real auth.
- Elapsed-day calculations now use UTC consistently (`assignment.clock.today()`)
  rather than server-local time, but this still doesn't account for a
  given user's own timezone in a geographically distributed program.
- Three CML platform questions are open and block only
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
