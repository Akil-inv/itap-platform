# ITAP Architecture

Status: Living document. Update this alongside code changes — it is not a
one-time design note. Whenever a capability's port, adapter set, or cutoff
rationale changes, update the corresponding row below in the same commit.

## Purpose

ITAP (Intern Training & Assignment Platform) was designed against an
8-block **capability catalog** concept: domain-agnostic building blocks
reusable, unmodified at the core, across future solutions by supplying
different configuration rather than different code.

**Decision (2026-09-12): build the working platform first.** Generalizing
before a second, real use case exists is speculative — we won't know if a
cutoff is actually correct until something else needs it. So blocks 2/3
(Assignment Engine + Rule Engine) are built directly against ITAP's own
vocabulary (Agent, Manager) rather than generic Subject/Holder naming, and
block 5 (Scoring & Closure) is folded into the same package rather than
split out. The ports/adapters discipline (below) is kept regardless — it's
cheap and pays for itself even in a single app — but we are not paying the
cost of full genericity, separate installable packages, or Drools/Flowable
adapters until ITAP works and a second use case actually asks for reuse.

The block map and cutoff principles below remain the target shape for
*if and when* this gets taken apart into a genuine catalog. Until then,
`capabilities/assignment/` intentionally violates the "no domain vocabulary"
rule — that's accepted debt, not a mistake, and is the first thing to
revisit during extraction.

## Governing principle: where to cut a block boundary

A boundary belongs wherever any of the following is true. If none are true,
merge the code into its neighbor rather than over-fragmenting:

1. **Different rate of change** — decision *policy* (which conditions
   trigger what) changes often; orchestration *mechanics* (how a multi-step
   process waits/resumes) changes rarely. Different rate of change implies a
   different block.
2. **Vocabulary shift** — the moment generic code would need to know a
   domain noun ("Intern", "Ticket", "Work Order"), stop. That is a
   port/config seam, not a continuation of the same block.
3. **Plausible swap-out** — if an implementation could plausibly be
   replaced without touching its neighbors (Postgres → Impala, hand-rolled
   rules → Drools, SMTP → Slack), it must already sit behind an interface,
   even while only one implementation exists.
4. **Single reason to change** — each block breaks for exactly one kind of
   reason. If a bug fix in "how assignments transition" ever requires
   touching "how reminders are worded," the boundary is wrong.

## Layered view

```
                    ┌───────────────────────────────────────────┐
   FRONT DOORS      │  Streamlit UI (ITAP)   │  future: REST API │   consumers only —
                    └────────────┬──────────────────────────────┘   not part of the catalog
                                 │ calls capability ports only
        ┌────────────────────────┼─────────────────────────────────────┐
        │                        ▼                                       │
        │   CAPABILITY LAYER (domain-agnostic — this IS the catalog)      │
        │                                                                   │
        │  1 Party/Identity   2 Assignment Engine   3 Rule/Decision Engine  │
        │  4 Process Orchestration  5 Scoring & Closure  6 RBAC Scope       │
        │  7 Notification Dispatch  8 Outbox/Event Sync                     │
        └────────────┬──────────────────────────────────────────────────┘
                      │ each capability depends only on its OWN port(s)
        ┌────────────▼──────────────────────────────────────────────────┐
        │  ADAPTER LAYER (swappable, infra-specific, never imported        │
        │  by anything in the capability layer)                             │
        │  Postgres repo · Drools/DMN or in-process rules · Flowable or      │
        │  in-process FSM+timer · SMTP/Slack sender · Iceberg sink            │
        └───────────────────────────────────────────────────────────────┘
```

## The 8 capability blocks

| # | Block | Agnostic core | What gets injected per domain | Port(s) | Cutoff rationale |
|---|---|---|---|---|---|
| 1 | **Party/Identity** | A Party: an addressable actor with attributes + relationships to other Parties | Party *types* (Agent/Manager/Owner, or Requester/Technician) | `PartyRepo` | Every other block needs "who"; none of them should define who |
| 2 | **Assignment Engine** | Subject↔Holder binding over a period; holds current state | Entity names, valid state list | `AssignmentRepo`, emits transition events | Owns *state*, not *when/why* it changes — that is blocks 3/4 |
| 3 | **Rule/Decision Engine** | Given (state, event, context) → verdict + actions | The transition table itself (YAML/DMN) | `RuleEngine.evaluate()` | Synchronous, stateless, swapped constantly — must stay decoupled from orchestration |
| 4 | **Process Orchestration** | Long-running processes: waits, timers, escalations; calls back into 2/3 | The process definition (which timers, which escalation path) | `ProcessOrchestrator` | Asynchronous/stateful over time — different execution model than block 3 |
| 5 | **Scoring & Closure** | A structured record attached to an Assignment's closure, gated by a rule | The record *shape* (ITAP: objective+subjective+reverse feedback; ticket: resolution+CSAT) | `ClosureRecorder` | The most domain-variable artifact — isolated so the engine never needs to know its shape |
| 6 | **RBAC Scope** | "Can Party X see Record Y", computed from relationships, not hardcoded per-role queries | Which relationship implies which visibility (owns / assigned-to / org-of) | Decorator over any repo read | Cross-cutting; used by everything, owned by nothing else; must never leak into blocks 2/5's queries |
| 7 | **Notification Dispatch** | Send message M to Party P via channel C | Message templates, channel choice | `Notifier.send()` | Pure effector, deliberately dumb — *who decides to notify* lives in block 4 |
| 8 | **Outbox/Event Sync** | At-least-once delivery of "what happened" to an external sink | The sink implementation (Iceberg today) | `EventSink` | Persistence-adjacent infra concern, orthogonal to what the events mean |

No ITAP-specific code should exist inside blocks 1–8. If it does, the cutoff
was drawn in the wrong place — fix the boundary, don't work around it.

## ITAP as configuration over the catalog

ITAP itself is intended to be almost entirely configuration on top of the
8 blocks:

- Party types: `Agent`, `Manager`, `FunctionalOwner`
- Assignment transition table: goal-setting-not-a-gate, cross-team
  bifurcation, manager-requested extension
- Process definitions: goal-setting reminder timer, minimum-elapsed-time
  before feedback is allowed
- Closure record shape: objective + subjective assessment, plus reverse
  feedback from Agent about Manager
- RBAC config: Manager sees their own Agents; Agent sees only their own
  history; Functional Owner sees everything plus consolidated per-Agent
  scoring

## Deployment target: CML

- The Streamlit UI runs as a **CML Application**.
- The system of record is **Postgres**, reachable over the CML workspace
  network (co-located or external — see open platform questions below).
- The Outbox → Iceberg sync (block 8's adapter) runs as a separate
  **CML Job**, decoupled from the Application's lifecycle.
- Blocks 3 (Rule Engine) and 4 (Process Orchestration) ship with a simple
  in-process adapter first (YAML transition table; FSM + timer loop).
  Drools (DMN) and Flowable (BPMN) are candidate future adapters behind the
  same ports — adopting them does not require touching capability code,
  only registering a new adapter.

### Open platform questions (need confirmation from CML admin/platform team)

1. Package/runtime rights: can Postgres be installed user-space (conda-forge)
   at session start, or does a custom CML Runtime image need to be built and
   registered?
2. Internal networking: can one CML Application reach another CML
   Application (or a CML Job) over a raw TCP port within the workspace, or
   only via the external HTTP ingress?
3. Whether Impala/Iceberg is required as the live system of record, or
   whether landing data there for governance/reporting (via the outbox
   sync) is sufficient. Current design assumes the latter.

These block Phase 2+ (Iceberg sync, Flowable/Drools adapters) but do not
block Phase 1 (Party/Identity + Assignment Engine + Rule Engine, all
runnable against Postgres with an in-process rule adapter).

## Build order

1. **Party/Identity** — done. Domain model, `PartyRepo` port, in-memory +
   SQL adapters, contract tests passing.
2. **Assignment Engine + Rule Engine + Scoring & Closure** — done, as
   `capabilities/assignment/`. Covers: create assignment (goal-setting not
   a gate, rejects end_date < start_date, rejects a duplicate active
   Agent/Manager pair), manager-only extension (rejects shortening —
   new_end_date must be later than the current one), cross-team
   bifurcation (independent Assignment records per manager),
   min-elapsed-and-goal-setting-gated closure with objective+subjective
   scoring (score bounds validated at the domain level, not just the UI
   slider), reverse feedback (gated by the same minimum-elapsed period as
   closure, not by assignment state), two administrative closure paths
   not gated by minimum-elapsed or goal-setting (`withdraw_assignment` —
   Agent leaves early, no score; `reassign_all_from_departing_manager` —
   Manager leaves, bulk-closes and reopens their team under a new
   manager), optimistic concurrency (a `version` column; a write against
   a stale copy raises `ConcurrentModification` instead of silently
   overwriting a concurrent change), and overdue-goal-setting /
   overdue-closure queries for a future reminder job, and an optional structured `criteria` checklist on GoalSetting (a lightweight scoring rubric, consumed by the bulk-import feature). 59 tests passing
   across in-memory + SQL adapters. Built directly with ITAP's
   vocabulary — see "Decision" note above.

   The earlier Manager-facing `swap_to_new_manager` (self-service,
   scored) was **removed** (2026-09-12, gap-analysis pass) — it let a
   Manager unilaterally hand an Agent to whichever peer they chose,
   conflicting with the spec ("central team can swap them"). The normal
   rotation-swap case now composes two already-existing primitives
   instead: Manager closes normally (scored) once tenure completes;
   Functional Owner creates the next Assignment via Onboard & Assign.
   `reassign_all_from_departing_manager` is a genuinely different case
   (no score — it's not a performance moment) and is
   Functional-Owner-only via RBAC.

   **`kind` (2026-09-12, associate-journey redesign, Phase 1):** `Assignment`
   gained `kind: AssignmentKind` (`PRIMARY` / `SECONDARY` / `CCA`), per
   `docs/associate_journey_redesign.md`'s "Episode / Engagement /
   Assignment" section — the same record, three names depending on whose
   screen it's on (Associate: Episode, Manager: Engagement, Admin:
   Assignment), and one of three kinds regardless of the label. Defaults
   to `PRIMARY` for backward compatibility, so every existing call site
   and every Assignment created before this field existed keeps its
   original meaning unchanged. The existing cross-team bifurcation
   capability (same Agent, concurrent Assignments under different
   Managers) is the Secondary case going forward — `test_assignment_service.
   py::test_cross_team_bifurcation_each_assignment_independent` now
   creates its two assignments as PRIMARY + SECONDARY to say so
   explicitly, though the underlying mechanics (independent records,
   independent scoring) are unchanged.

   **Judgment call:** the spec states "exactly one Primary is active at a
   time," which reads like a rule this layer should enforce. It
   deliberately isn't enforced here: several already-passing tests
   (`test_list_overdue_goal_setting_reflects_reminder_need`,
   `test_reassign_all_from_departing_manager`, and bifurcation itself)
   create the same Agent under two Managers via the plain
   `create_assignment(...)` call with no `kind` argument, i.e. two
   PRIMARYs by default — exactly the case a hard guard would reject. This
   is Phase 1 (data-model only, per the redesign's own sequencing); the
   actual one-Primary invariant is a UI/workflow concern (which action
   the associate/manager/admin took — "start a new Primary" vs. "add a
   Secondary" — not something inferable from the data alone), and
   belongs in whichever later phase wires the "add a Secondary" /
   "advance to next Primary stage" actions described in the spec's
   "Associate portfolio" section. Revisit then.
3. **RBAC Scope** — done, as `capabilities/rbac_scope/`.
   `ScopedAssignmentQueries` computes visibility from the Viewer's
   relationship to each Assignment (manager_id/agent_id match), not from
   separate per-role queries. Child records (GoalSetting, ClosureRecord,
   ReverseFeedback) inherit their parent Assignment's visibility.
   Functional Owner also gets `consolidated_score(agent_id)` — an average
   objective_score across an Agent's closed assignments; Agents may query
   only their own, Managers not at all (per spec: their scope stays
   limited to what pertains to their own assignments). `list_overdue_closure`
   and `reassign_all_from_departing_manager` (Functional-Owner-only) added
   in the same gap-analysis pass as the service-layer changes above.
   13 tests passing. Required adding `AssignmentRepo.list_all()` for the
   Functional Owner's blanket-visibility need.
4. **Streamlit UI** — done, as `apps/streamlit_ui/`. Thin front door over
   `party_identity` + `assignment` + `rbac_scope`; no business logic of
   its own. Identity is a dev-mode landing/sign-in page (`home.py`) —
   not a sidebar dropdown — storing the chosen person in
   `st.session_state`; real auth is still an open platform question and
   only touches this one seam when answered. Page headings are
   product/task-oriented ("My Team", "My Journey", "Workforce Overview"),
   not the signed-in person's name or role. `theme.py` and `journey.py`
   render each Assignment's existing state as a visible 3-stage stepper
   (Goal Setting → Active → Closed) instead of a flat form dump.
   `org_tree.py` renders the whole current org (Functional Owner(s) →
   Managers → Agents) as a hand-built inline SVG — rounded cards, smooth
   bezier connectors, hover-to-trace highlighting — with zero external/
   CDN dependency. Verified end to end with `smoke_test.py` (Streamlit's
   `AppTest`, headless) and with real Playwright screenshots (AppTest
   doesn't render CSS/JS, so a visual claim needs a real browser to back
   it).
5. **Notification Dispatch**, **Process Orchestration** (real
   reminder timers, not just the query) — next. The UI currently only
   surfaces the overdue-goal-setting list; there is no delivery
   mechanism yet.
6. **Outbox/Event Sync** — added once the CML platform questions above are
   answered.

### Known MVP decisions to revisit (documented, not blocking)

- Minimum elapsed period before closure/feedback: 30 days, configurable
  per `AssignmentService(min_days_before_closure=...)` — not yet
  surfaced as an admin-editable setting.
- ClosureRecord and ReverseFeedback are append-only by design (no update
  method) for audit/dispute integrity — confirmed acceptable for v1.
- `date.today()` calls were replaced with `assignment.clock.today()`
  (UTC-based) throughout the `assignment` package, removing server-host
  timezone ambiguity — this does not solve per-user local time for a
  geographically distributed program, just standardizes the server-side
  clock.
- No field yet reserved for an external identity (email/SSO subject) as
  a first-class Party attribute — `attributes["email"]` is populated
  optionally by the onboarding forms as a convention, not enforced or
  validated. Whatever real auth eventually maps against should confirm
  this convention or replace it.
- `ITAP_DEV_MODE=false` hides the identity-switching UI but is a safety
  valve, not a security boundary — the underlying service calls have no
  auth of their own yet. Real auth remains the actual fix.
- Linking a stage to its Assignment is still a manual admin action for
  the *first* Assignment in a plan (nothing creates that one for you at
  enrollment time) — but once a stage has a default Manager configured
  (see "Auto-creating the next Assignment" below), every stage after
  that links and creates itself automatically as the plan progresses.
  Stages with no default Manager still work exactly as before: manual
  "Advance" and manual "Link."

### Rotation Plan (2026-09-12, same day)

A new capability, `capabilities/rotation_plan/`: a fixed, named path of
stages (e.g. "Platform Team" -> "Data Team" -> "Product Team") that an
Agent is enrolled into, so their next placement isn't a one-off decision
each time. Domain: `RotationPlan` (name, ordered `stage_names`,
`weeks_per_stage`) and `Enrollment` (which plan, which Agent, current
stage index, when the current stage started) — same hexagonal shape as
every other block (`ports.py`, `adapters/{in_memory,sql}.py`,
optimistic concurrency on `Enrollment` via `version`). 49 tests passing.

`RotationPlanService.progress_value()` computes a fractional position
along the plan (completed stages + elapsed-time-in-current-stage /
`weeks_per_stage`, clamped just under the next integer) — the number the
UI's "journey curve" plots a marker at. This surfaced a real bug during
manual verification: SQLite drops datetime tzinfo on round-trip
regardless of the column's `timezone=True` flag, so an `Enrollment` read
back via the SQL adapter had a naive `stage_started_at`, and subtracting
it from `datetime.now(timezone.utc)` raised
`TypeError: can't subtract offset-naive and offset-aware datetimes`.
Fixed with a small `_as_utc()` normalizer in the service (treat any naive
datetime as UTC, since everything here is always written as UTC); the
`assignment` package never hit this because its elapsed-time math uses
`date`, not `datetime`. Caught by re-parametrizing the service tests over
both adapters (mirroring the repo contract tests) rather than only the
in-memory one — worth remembering for any future service whose tests
started against `InMemory*` only.

`apps/streamlit_ui/journey_curve.py` is a Python port of the curve from
the approved front-page mockup (a standalone HTML/JS artifact, not part
of this repo): a winding, ascending bezier path (not a straight
timeline), rendered as inline SVG via `st.iframe` — same
zero-external-dependency convention as `org_tree.py`. Two render modes:
a single "you are here" marker with the traveled portion drawn solid and
the rest dashed (Agent's "My Journey"), or one colored dot per enrolled
Agent on a shared plan curve (Functional Owner's "Rotation Plans" tab,
"where everyone stands").

Functional Owner gets a new "Rotation Plans" tab: create a plan (name +
semicolon-separated stages + weeks/stage), enroll an Agent, see the
cohort plotted on the plan's curve, and manually advance a person's
stage. Agent's "My Journey" shows their own plan curve (if enrolled)
above the existing per-Assignment cards, which are unchanged.

### Linking a stage to its Assignment (2026-09-12, same day)

Closed the gap the Rotation Plan section above documented: a stage was a
bare label with no record of which Assignment/Manager actually covered
it. `Enrollment` gained `stage_assignments: dict[int, UUID]` — stage
index -> `assignment.Assignment` id, by id only (this package still never
imports `assignment`; the Streamlit app layer, which already talks to
both capabilities, is what resolves an id to a Manager name). New
`RotationPlanService.link_assignment(enrollment_id, stage_index,
assignment_id)`; `enroll()` and `advance_stage()` both grew an optional
`assignment_id` param to link in the same call instead of a second one.
`Enrollment.current_assignment_id` is a convenience property for "the
assignment covering *today's* stage." 71 tests passing (up from 49).

The SQL adapter needed the same additive-column self-heal
(`_ensure_columns`, backfilling `stage_assignments` to `{}`) as
`assignment` did for `criteria`/`version` — this table is only one commit
old, but the convention held anyway rather than assuming "we just built
this, it can't be stale yet." Storage detail: JSON object keys must be
strings and `UUID` isn't JSON-serializable, so the adapter encodes both
the stage index and the assignment id as strings and decodes them back
to `int`/`UUID` on the way out — the domain layer never sees a string key.

UI: the Functional Owner's per-enrollment row is now an expander showing
who currently covers that stage (or that no one does yet), a selector of
the Agent's own active Assignments to link, and the existing "Advance"
action below it. The Agent's journey curve passes the resolved Manager
names as `stage_subs`, so their own page shows who covered each reached
stage without a manager having to be looked up separately.

Manual verification (not just the unit suite) caught a real layout bug
this surfaced: when the "you are here" marker lands exactly on a stage
node — true at progress 0, and true again immediately after any
`advance_stage` call — its "You are here" caption used to sit on the
same side as that node's own name label, and a stage's new manager
sub-label (`stage_subs`) sat close enough to overlap the marker's halo
outright. Fixed in `journey_curve.py`: the sub-label offset moved from 6
px off the node (inside the halo's 13 px radius) to 34 px, and "You are
here" now renders on the side opposite that node's own labels instead of
always above. Caught by a Playwright screenshot of the Agent's own page
after linking an assignment, not by any unit test — the math was correct
in every automated test; the labels only visibly collided once real text
occupied both slots.

### Auto-advancing on Assignment closure (2026-09-12, same day)

Closing an Assignment linked to an Enrollment's current stage now
auto-advances that stage — the manual "Advance" button in Rotation Plans
is still there for the unlinked/no-Assignment case, but the common path
(a stage has a linked Assignment, that Assignment closes) no longer needs
it. Lives in `apps/streamlit_ui/rotation_plan_bridge.py`, not in either
capability: `rotation_plan` still never imports `assignment`, so the one
place allowed to know about both is the app layer that already wires
them together. `advance_linked_stage_if_closed(services, assignment_id)`
looks up the closed Assignment's Agent, checks whether any of their
Enrollments has that Assignment as its *current* stage's link, and calls
`RotationPlanService.advance_stage` if there's a next stage to move to —
a no-op (not an error) when the Assignment isn't linked to anything, or
was already the plan's last stage.

Called after all three ways an Assignment can close: a Manager's normal
close, a Manager's withdrawal, and the Functional Owner's manager-handoff
bulk close (looping once per closed Assignment, since that action closes
a whole team's worth at once). Deliberately advances on *any* closure
reason, not just `"completed"` — the stage is over either way, whatever
the reason; only whether the Agent scored well is reason-dependent, and
that's an separate, already-existing concern (`ClosureRecord`).
Failures inside the bridge are swallowed rather than raised: an
auto-advance is a convenience, and it must never turn an otherwise-
successful Assignment closure into a visible error for the person who
just closed it.

New `apps/streamlit_ui/test_rotation_plan_bridge.py` (same bare-script
convention as `test_bulk_import.py`) covers: a linked stage advancing on
closure, closing an Assignment linked to the *last* stage doing nothing,
and closing an Assignment with no plan link at all doing nothing. Verified
end to end with Playwright too: linked Casey's Platform-Team stage to her
Alex assignment, withdrew that assignment as Alex, and confirmed Casey's
own journey curve had already moved to Data Team with no admin action in
between.

### Auto-creating the next Assignment (2026-09-12, same day)

Closed the remaining manual step: `RotationPlan.default_stage_managers`
(a stage index -> Manager id map, same by-id-only shape as
`Enrollment.stage_assignments` — `rotation_plan` still imports neither
`assignment` nor `party_identity`) lets an admin configure, per plan,
which Manager should pick up a given stage. `RotationPlanService` grew
`set_default_manager(plan_id, stage_index, manager_id)` (pass `None` to
clear one) and `create_plan(..., default_stage_managers=...)`; both
`RotationPlan` and the `rotation_plans` table gained a `version` column
for the same optimistic-concurrency contract `Enrollment` already had —
`update_plan` is the new corresponding port method. 91 tests passing (up
from 71).

`rotation_plan_bridge.advance_linked_stage_if_closed` now checks the new
stage's `default_stage_managers` entry before just moving the index: if
one exists, it creates a real Assignment (`assignment_service.
create_assignment`, using `assignment.clock.today()` per the existing
UTC-clock convention) under that Manager and links it in the same call
to `advance_stage`. A `DuplicateAssignment` (the Agent already has an
active Assignment with that Manager — plausible under bifurcation) or
any other `ValueError` falls back to advancing unlinked, same as a stage
with no default Manager at all — this is a convenience, and a
partially-successful automatic action beats a broken one every time.

UI: each plan in the Functional Owner's "Rotation Plans" tab has a new
"Default manager per stage" expander — one selectbox per stage
(including "— none —"), saved together. The per-enrollment expander's
existing "Link an active Assignment to this stage" control is unchanged
and still the way to fix up a stage with no default Manager, or to
override an auto-created link.

`test_rotation_plan_bridge.py` gained two cases: a stage with a default
Manager gets a new Assignment auto-created and linked, and a stage with
no default Manager still just advances (unchanged, no regression).
Verified end to end with Playwright: configured Priti as Data Team's
default Manager, withdrew Casey's Platform-Team assignment, and
confirmed — without touching anything else — her Rotation Plans row read
"Covered by Priti" with a brand-new active Assignment, and her own
journey curve showed the same.

### Bulk Setup + a real Streamlit ordering bug (2026-09-12, same day)

`apps/streamlit_ui/bulk_import.py`: upload an Excel workbook (Agents,
Managers, Assignments, Criteria Library sheets — template generated on
demand, not a bundled file) to set up a baseline in one pass instead of
one form per row. Two-phase parse-then-confirm, matches by email/name to
stay idempotent on re-upload, per-row errors don't abort the batch. This
motivated `GoalSetting.criteria: list[str]` — a lightweight, optional
scoring-rubric checklist attached to goal setting (closure still records
one objective_score + notes; criteria just make explicit what that score
should be judged against — the "full per-criterion rubric" alternative
was considered and deliberately deferred).

Building this surfaced a genuine Streamlit bug worth documenting: **all
tabs render in one script pass, in a fixed order.** Org Structure/All
Assignments are earlier tabs than Bulk Setup, so within a single pass
they're computed *before* an import in Bulk Setup runs — a successful
import couldn't retroactively update what already rendered earlier in
that same pass. It looked exactly like a caching bug (stale content
persisting in-session, correct after a hard reload) but wasn't — the
data was correct, the render order was wrong. Fixed with `st.rerun()`
after a successful import, stashing the result in `st.session_state`
first so the confirmation message survives the rerun instead of
vanishing with it. Every other mutation in the app already had
`st.rerun()` immediately after its write — this was the one place that
didn't, because the flash-message need wasn't obvious until visual
verification (a fresh Playwright screenshot after import, compared
against one after a hard page reload) caught the discrepancy. Convention
going forward: any new mutating action needs `st.rerun()` right after
its write.

### Self-healing additive-column migration (2026-09-12, same day)

A real-world gap surfaced when a user pulled the `criteria`/`version`
changes and ran the app against their existing local `itap.db`:
`sqlite3.OperationalError: no such column: goal_settings.criteria`.
Root cause: `metadata.create_all()` only creates missing *tables* — it
never adds missing *columns* to a table that already exists on disk. Any
local dev database created before a column was added to the schema
definitions is permanently out of sync with the code, with no recovery
path except deleting the file.

Fixed in `capabilities/assignment/src/assignment/adapters/sql.py` with
`_ensure_columns(engine, table, backfill)`: after `metadata.create_all()`,
it inspects the actual on-disk table (`sqlalchemy.inspect`), diffs its
columns against the table's ORM definition, and issues
`ALTER TABLE ... ADD COLUMN ...` for anything missing, backfilling
existing rows where the column can't sensibly stay `NULL` (`version`
defaults to `0`, `criteria` defaults to `[]`; `closure_note` needs no
backfill — it was already nullable). This runs automatically on every
`create_schema()` call, so an old local database self-heals on next app
start with no manual steps. Explicitly **not** a real migration framework
(no down-migrations, no rename/drop support, no versioning) — revisit
with Alembic if schema evolution outgrows this. Verified by hand-building
a SQLite file with the pre-`criteria`/pre-`version` schema and confirming
`create_schema()` + a live query both succeed against it; full test
suites (`party_identity` 13, `assignment` 59, `rbac_scope` 13) plus
`smoke_test.py` and `test_bulk_import.py` all still pass.

### Catalog capability (2026-09-12, associate-journey redesign, Phase 1)

New `capabilities/catalog/`: the Setup/Configuration data the redesign
spec (`docs/associate_journey_redesign.md`) calls for — Skills, Teams,
and CCA-activity catalogs (admin-maintained master data, seeded from
Excel, addable via the app) — plus the small associate-declared records
that go with them in the spec's "Associate flow": self-declared/
engagement-sourced skills, the associate's own lean profile (bio,
experience, project highlights, photo), standing interest flags in
Teams/CCAs, and informational annual leave. Same hexagonal shape as
every other block (`ports.py`, `adapters/{in_memory,sql}.py`,
`service.py`, contract tests parametrized over both adapters). 69 tests
passing.

**Where this lives, and why:** none of this belongs inside `assignment`
— it has a different rate of change (admin/associate direct edits, no
rule engine, no guarded state machine, no workflow) and a different
"single reason to change" (Setup master data and self-service profile
data change for reasons entirely unrelated to why an Assignment
transitions). It also doesn't belong in `party_identity`, which is
still the one block meant to stay domain-agnostic (see the "Decision"
note above — `assignment` is the *accepted* exception, not a precedent
to extend); shoving ITAP-specific concepts like "annual leave" or a
"CCA activity" into Party's generic `attributes` dict would work
mechanically but would be exactly the kind of vocabulary leak block 1's
own README warns against. `catalog/` is a new, small, still
domain-specific block (matching the project's current "don't chase
genericity yet" decision) purpose-built for this one cohesive group of
admin/associate-declared data. Like `rotation_plan`, it never imports
`assignment` or `party_identity` — Agent/Manager ids are opaque UUIDs
here, resolved to names by whichever app-layer code already talks to
all of them.

**Judgment call — one capability, not several:** Skills/Teams/CCA
catalogs (admin Setup, low churn) and the associate-declared records
(interest flags, leave, profile, self-declared skills — higher churn,
associate-editable) are arguably two different bounded concerns by the
architecture's own "different rate of change" heuristic. They were kept
in one small package rather than split into two near-empty capabilities:
the associate-declared records either directly reference a catalog
entry by id (an `InterestFlag`'s `target_id` is a `Team`/`CcaActivity`
id) or are trivial single-entity records (`AnnualLeave`) that don't
justify a whole new package on their own. If either side grows
materially (e.g. leave gains its own approval workflow later, despite
the spec currently ruling that out), split it out then — this is
explicitly a "don't over-engineer for a need that doesn't exist yet"
call, not a permanent stance.

**`InterestActivity`** is the `raised_at`/`seen_at` pair the admin's
associate list needs to compute the "interest changed" highlight badge
(`CatalogService.has_unseen_interest_change`): `raised_at` moves forward
on every flag/unflag, `seen_at` moves forward when the admin opens that
Associate's profile (`mark_interest_seen`) — the exact "flag changes it,
opening the profile clears it" pattern the spec describes, without a
history log per change (the spec only asks for a boolean-ish highlight,
not an audit trail).

**Not built in this pass (deliberately, per the task's Phase 1 scope):**
no Streamlit views wire these catalogs up yet (Setup screens, the
associate's profile editor, the admin list's highlight badge rendering)
— that is explicitly later-phase UI work. `bulk_import.py`'s Excel
parsing is also untouched; teaching it to seed Skills/Teams/CCA rows
from the workbook is a separate, later pass per the task's instructions.

### Associate-journey admin UI (2026-09-12, associate-journey redesign, Phase 2)

Wired `capabilities/catalog` into the Streamlit app (`services.py` gained
`catalog_repo`/`catalog_service`) and built the Functional-Owner-facing
screens from `docs/associate_journey_redesign.md`'s "Admin flow" section.
Manager/Associate views (`views/manager.py`, `views/agent.py`) are
untouched — later phases.

- **Associates list** (`views/functional_owner.py._associates_list`,
  replacing the old flat "All Assignments" tab): one row per Agent.
  `battery.py` computes the tenure battery bar from the Agent's
  PRIMARY-kind Assignments only (Secondary/CCA never contribute their
  own segment, per spec — the Primary spine is what drives tenure);
  `associate_status.py` classifies each Agent into the spec's four
  filter buckets. The hidden aggregate score reuses `ScopedAssignmentQueries.consolidated_score` (already averages every closed
  Assignment of any kind, so no new scoring logic was needed) and sits
  behind an `st.popover` — chosen as the closest native Streamlit
  primitive to the spec's "reveal on click, then hide again" bank-balance
  interaction; there is no dedicated widget for that pattern. The
  interest-change badge reuses `CatalogService.has_unseen_interest_change`
  outright.
- **Associate Portfolio** (`views/associate_portfolio.py`, new — level 2,
  reached by clicking a name, not a tab): profile section over
  `CatalogService` (bio/photo/experience/highlights/skills, admin-editable
  on the Associate's behalf); a rotation timeline built from the Primary
  spine, each stage expandable to its "N responsibilities" (Secondary/CCA
  anchored to the Primary stage active on the episode's start date, per
  the spec's overlap rule); read-only interest flags; and the actions
  that used to be separate top-level tabs (close + optionally advance to
  a new Primary in one step, add a Secondary, log a CCA), now scoped to
  this one Associate instead of scattered across the app. Opening the
  page calls `mark_interest_seen` immediately, per spec ("opening the
  profile is what clears it").
- **Setup** (`views/setup.py`, new top-level tab): three columns over
  `CatalogService` (Skills/Teams/CCA), each a plain list + add-new form.

**Judgment calls made this pass (spec left them open):**

- **Status filter thresholds** — `associate_status.py`'s module
  docstring is the source of truth: Active = active Primary, nothing
  overdue; Needs attention = active Primary flagged by the *existing*
  overdue-goal-setting/overdue-closure queries (reusing those thresholds
  instead of inventing new ones); Available = no active Primary but not
  fully wound down (mid-gap, possibly with an active Secondary/CCA, or
  never had a Primary yet); Completed = no active Assignment of any
  kind AND the most recent Primary closed with `closed_reason ==
  "completed"` (a withdrawn/cut-short Primary, or a still-active
  Secondary/CCA, keeps the Agent in "Available" instead).
- **Setup catalog "source" column** — the task's mockup description
  calls for showing whether a catalog entry came from Excel or was
  "added here." Skill/Team/CcaActivity carry no `source` field (Phase 1
  didn't add one, and `bulk_import.py` doesn't seed these catalogs from
  Excel yet — see the Catalog capability section above), so fabricating
  the distinction in the UI would show data that doesn't exist. `views/
  setup.py` says plainly that every entry currently reads as "added
  here" instead. Revisit once bulk_import seeds these catalogs and a
  `source` field is worth adding.
- **App-layer demo seed data** (`app.py._seed_demo_data`): updated the
  existing Casey/Bailey cross-team-bifurcation demo assignment to
  `kind=AssignmentKind.SECONDARY` (it was created via the plain,
  kind-less `create_assignment` call before this pass, defaulting to a
  second PRIMARY) — otherwise the new Portfolio page showed Casey with
  two independent "Current" Primary stages instead of one Primary with a
  nested Secondary responsibility, which is exactly the case the
  "kind" note under block 2 above already says this scenario should be
  going forward.

Verified with a new `test_admin_journey_ui.py` (`AppTest`, same
convention as `smoke_test.py`) plus a real Playwright pass
(`screenshot_admin_journey.py`) against the running server; all
pre-existing suites (`smoke_test.py`, `test_bulk_import.py`,
`test_rotation_plan_bridge.py`, and the `catalog` package's own 69
tests) still pass unchanged.

### Associate-journey manager UI (2026-09-12, associate-journey redesign, Phase 3)

Built the Manager-facing screens from `docs/associate_journey_redesign.md`'s
"Manager flow" section: `views/manager.py` (rewritten — was previously a
flat per-Assignment list combining goal-setting/extension/close/withdraw
inline) is now the **My Team** entry point, and a new `views/
manager_associate.py` is the level-2 per-Associate page it drills into,
same "level 2 page via session_state" pattern as
`views/associate_portfolio.py`. Admin views (Phase 2) and the Associate/
Agent view (`views/agent.py`, still a later phase) are untouched. Model
changes live in `capabilities/assignment` (`domain.py`, `ports.py`,
`service.py`, both adapters) — none of this needed a new capability
package, since goal freezing, scoring, and change-requests are all
still properties of an *Assignment*, not a new bounded concern.

- **My Team** (`views/manager.py`): **Current** / **Rolled Off** tabs,
  scoped to `AssignmentRepo.list_by_manager`. Current = any Assignment of
  any kind still ACTIVE under this Manager. Rolled Off (judgment call —
  the spec only says "associates who've since moved to a different
  manager", the exact detection rule was left open) = this Manager's
  most recent Primary with the Associate has CLOSED, *and* the Associate
  has since started a Primary under a different Manager on or after that
  close date — i.e. the relationship is genuinely over, not a mid-gap
  Available stretch. An Associate whose only history with this Manager
  was a Secondary/CCA, or whose Primary closed but who hasn't started
  anywhere else yet, appears in neither tab; both are documented in
  `manager.py._classify`'s own docstring. Reuses `battery.py` unchanged
  for the tenure bar. **No score of any kind renders on this page** —
  per spec this is a hard rule ("Aggregate score is never visible to a
  manager ... for anyone but themselves" refers to a score they gave on
  one episode's own Review & Scoring tab, never a rolled-up number on
  this list), not a UI nicety, so unlike the admin's list there is no
  hidden/eye-icon reveal here at all.
- **Manager's Associate page** (`views/manager_associate.py`, new):
  three tabs matching the approved mockup's structure — **Profile**
  (read-only catalog data, no edit affordance: editing belongs to the
  Associate's own page, a later phase), **Goals**, **Review & Scoring**.
  Judgment call: the mockup shows one Goals/Review & Scoring pair per
  Associate page, but the domain allows a Manager to hold more than one
  concurrent Assignment with the same Associate (Primary + a CCA they
  personally organize, say) — an engagement selector appears only when
  this Manager has more than one ACTIVE Assignment with this Associate;
  with exactly one (the common case) it's chosen silently.

**Where the frozen state lives**: both new records are kept inside
`capabilities/assignment`, not `catalog` — they're properties of one
specific Assignment/episode's lifecycle (frozen goals gate closure,
frozen scores feed a Closure request), which is squarely `assignment`'s
existing "rate of change" (guarded state, gated by service-level rules),
not `catalog`'s (admin/associate direct-edit master data, no rule
engine). Concretely:

- `GoalSetting` (existing dataclass) gained `frozen: bool`,
  `agreed_by: Optional[UUID]`, `agreed_at: Optional[datetime]`.
  `AssignmentService.record_goal_setting` stays the same upsert it always
  was (raises the new `GoalSettingFrozen` if called against an
  already-frozen record); `freeze_goal_setting` is the manager's "Agree
  & Freeze" action; `reopen_goal_setting` is the admin-only unfreeze —
  see "Deferred" below.
- A new `ReviewScore` dataclass (assignment_id, `criterion_scores: dict[str,
  float]`, a computed `objective_score`, notes, frozen) —  deliberately
  **not** the existing `ClosureRecord`: `ClosureRecord` is written once,
  atomically, at the moment `close_assignment` actually transitions an
  Assignment to CLOSED; `ReviewScore` is recorded against a *still-active*
  Assignment (the spec's Review & Scoring tab happens before the Closure
  request, let alone its approval). `AssignmentService.submit_review_score`
  always computes `objective_score` as the simple average across
  `criterion_scores` server-side (per spec — "simple average, no
  weighting") rather than trusting a UI-computed number; if a
  Assignment's `GoalSetting.criteria` is empty, the UI falls back to one
  ad-hoc `"Overall"` criterion so there's exactly one scoring code path
  either way.

**The Extension/Closure request mechanism (new, gated) vs. the existing
direct calls**: a new `ChangeRequest` dataclass
(`assignment_id`, `request_type` [EXTENSION/CLOSURE], `requested_by`,
`status` [PENDING/APPROVED/DENIED], `new_end_date` for EXTENSION,
`decided_by`/`decided_at`) plus `AssignmentService.request_change`
(creates a PENDING record only — does not itself extend or close
anything) and `approve_change_request`/`deny_change_request`. This is
**deliberately separate** from the pre-existing, direct
`request_extension`/`close_assignment` service calls, which keep their
current unapproved behavior unchanged for whatever already depends on
them (e.g. the admin's Associate Portfolio "Close current Primary &
advance" action, which is a central-team action, not a line manager's,
and was never meant to be gated the same way). `request_change` enforces
the spec's ordering: a CLOSURE request requires a frozen `ReviewScore`
already on file ("after scoring, the manager requests closure"); an
EXTENSION request requires a `new_end_date` later than the current
end/start date. **Withdraw stays exactly what it already was** —
`AssignmentService.withdraw_assignment`, called directly from the
manager's page, no request/approval record at all, per the spec's
explicit "direct, no-approval" carve-out for it.

**Deferred — explicitly out of scope for this pass**: the admin-side
approval screen for `ChangeRequest`s (a list of PENDING requests with
Approve/Deny buttons calling `approve_change_request`/
`deny_change_request`) is **not built**. The service methods and the
repo's `list_pending_change_requests` feed exist and are unit-testable,
but no view wires them up yet — that's a TODO for whichever pass adds
admin-facing request handling. Likewise, `reopen_goal_setting` and
`reopen_review_score` (the admin-only unfreeze actions the Goals/Review &
Scoring tabs both reference) have no admin screen calling them either —
the manager's page shows a **disabled** "Reopen ... (admin only)" button
in both places as an explicit placeholder/TODO, not a working control,
so the gap is visible in the UI rather than silently missing.

Verified with a new `test_manager_journey_ui.py` (`AppTest`, same
convention as `test_admin_journey_ui.py` — My Team's Current/Rolled Off
split and no-score guarantee, goal freeze, score submit-and-freeze, both
new request actions, and the direct Withdraw) plus a real Playwright
pass (`screenshot_manager_journey.py`); all pre-existing suites
(`smoke_test.py` — updated to drill into the new `manager_associate.py`
page instead of the old inline per-assignment panel,
`test_bulk_import.py`, `test_rotation_plan_bridge.py`,
`test_admin_journey_ui.py`, and all `capabilities/*` pytest suites, 253
tests total) still pass.

### Associate-journey associate UI + admin approvals (2026-09-12, associate-journey redesign, Phase 4)

Closed the last two gaps from `docs/associate_journey_redesign.md`: the
associate's own screens (`views/agent.py`, previously a single flat "My
Journey" page unchanged since before the redesign) and the admin
approvals screen both Phase 2 and Phase 3 explicitly deferred. Manager
(Phase 3) and admin Portfolio/Setup (Phase 2) screens are otherwise
unchanged.

**Piece A — `views/agent.py` rewritten as "My Journey"**, four tabs
(Profile / My Progress / Current Episode(s) / Leave & Interests) over
`catalog_service` + `assignment_service` + `ScopedAssignmentQueries`,
matching the approved mockup's structure as real Streamlit widgets
rather than its SVG pixel-for-pixel:

- **Profile** — the same self-editable bio/photo/experience/project-
  highlights/skills shape as the admin's Portfolio profile section
  (`views/associate_portfolio.py`), but pointed at the signed-in
  Associate's own `agent_id` and with one deliberate restriction: this
  page only ever calls `declare_associate_skill(..., SkillSource.SELF)`
  — an associate can never claim an engagement-sourced skill for
  themselves from their own page; that source only ever comes from the
  admin/manager side. Self-added skills need no verification (per spec)
  and render with the same "self-added" quiet label the admin's
  Portfolio page already used.
- **My Progress** — the existing rotation-plan-preview curve (unchanged
  from before this pass) plus two new sections: the associate's own
  aggregate score (`ScopedAssignmentQueries.consolidated_score`, which
  already refuses a Manager or a different Agent — the Agent asking
  about themselves always succeeds, so no new permission code was
  needed) and **score milestones**. **Judgment call — visualization**:
  the spec asks for "individual past episode scores... as milestones
  along their own learning curve" but explicitly doesn't require
  matching the mockup's SVG curve pixel-for-pixel in Streamlit. Chose a
  plain `st.bar_chart` (one bar per closed, scored episode, oldest
  first) plus a parallel ordered text list (kind, manager, close date,
  score) underneath it — the chart conveys "progression over time" at a
  glance, the list gives the exact numbers and is what an AppTest can
  actually assert against (Streamlit's native chart widgets aren't
  content-inspectable the way `st.markdown`/`st.write` are). No new
  domain logic: milestones are just `ScopedAssignmentQueries.
  get_closure_record` per closed-and-completed Assignment, sorted by
  close date.
- **Current Episode(s)** — same per-Assignment expander/stepper as the
  page had before, but the Goal Setting block is now the missing half of
  Phase 3's Goals tab: pre-freeze, an editable form
  (`AssignmentService.record_goal_setting` — the exact same upsert the
  manager's Goals tab calls) lets the associate key in their own
  proposed goals per spec ("the associate fills in proposed goals... and
  sees them once the manager agrees and freezes them"); once
  `GoalSetting.frozen` is true, the field disappears entirely and only a
  locked, read-only view remains. No new record type — this writes to
  the identical `GoalSetting` row the manager's `freeze_goal_setting`
  action reads and locks, which is the whole point: either side can key
  in the agreed text before the freeze, only the manager can freeze it,
  and once frozen neither can touch it again without an admin reopen
  (Piece B, below). The existing closure-score display and reverse-
  feedback form are otherwise unchanged.
- **Leave & Interests** — **Annual leave**: a plain start/end date-range
  form plus a chronological list, `CatalogService.declare_leave`/
  `list_leave` directly, no approval step or status field anywhere in
  the UI (per spec: purely informational). **Interest flagging**: every
  Team and CCA activity in the Setup catalogs renders as a row with a
  toggle button — "Flag interest: {name}" / "Remove interest: {name}" —
  calling `flag_interest`/`unflag_interest`. Copy above the section and
  on each row is deliberately explicit ("a general interest signal
  only... doesn't let you choose your next placement") per the spec's
  hardest requirement here: the UI must never imply flagging is a
  placement request. **This is exactly what feeds the Phase 2 admin
  highlight**: `flag_interest`/`unflag_interest` both already call
  `CatalogService._touch_raised` internally (unchanged from Phase 1),
  which moves `InterestActivity.raised_at` forward; the admin's
  Associates list badge (`has_unseen_interest_change`, built in Phase 2)
  reads that same field, so a flag/unflag from this new page lights up
  the existing badge with no new wiring on the admin side at all —
  verified end to end in both the new AppTest suite and the Playwright
  screenshots (below), not just by code inspection.

**Piece B — Admin Approvals (`views/approvals.py`, new top-level tab)**.
**Judgment call — its own tab, not folded into Setup**: Setup is
explicitly "not mixed into daily operational screens" per the spec —
Skills/Teams/CCA are configure-once-revisit-occasionally master data.
Approvals is the opposite: a queue of day-to-day, per-Associate/
per-Manager actions an admin works through regularly — much closer in
"rate of change" to the Associates list or the Overdue tab than to
Setup, per the same cutoff heuristic this document already uses
elsewhere. It sits in the nav right after Setup. Two sections:

- **Pending requests** — every PENDING `ChangeRequest`
  (`AssignmentService.list_pending_change_requests`, unused by any UI
  since Phase 3 added it) with Approve/Deny buttons calling
  `approve_change_request`/`deny_change_request` directly. Deny opens a
  small `st.popover` with an optional reason text area rather than
  denying on a single click — an irreversible negative decision on
  someone else's request gets a lightweight confirmation step; Approve
  doesn't need one since it's exactly what the requesting Manager
  already asked for. Approving a CLOSURE request also runs
  `rotation_plan_bridge.advance_linked_stage_if_closed` (same as every
  other place an Assignment can close), which Phase 3's deferral note
  hadn't needed to consider since nothing called `approve_change_request`
  from a view yet.
- **Reopen a frozen Goal Setting or Review Score** — a single Assignment
  picker (every Assignment, admin sees all per RBAC) showing whether its
  `GoalSetting`/`ReviewScore` is frozen, with a Reopen button for each
  that's actually frozen (`reopen_goal_setting`/`reopen_review_score`).
  No new query was needed on the repo — `list_all()` (already used by
  `ScopedAssignmentQueries` for the Functional Owner) plus the existing
  per-Assignment `get_goal_setting`/`get_review_score` getters were
  enough.

**Manager's disabled stub buttons, updated to point somewhere real**:
`views/manager_associate.py`'s two "(admin only)" reopen buttons stay
disabled — reopening is still never a self-service action for either
side, per spec — but their label/help text changed from a bare "TODO,
not wired yet" to "Ask admin to reopen (Functional Owner → Approvals)",
now that there's an actual admin screen to point at.
`test_manager_journey_ui.py` was updated for the new button label.

Verified with a new `test_associate_and_approvals_ui.py` (`AppTest`,
same convention as the other three UI test scripts) covering: self-
editing the profile and adding a self-declared skill, the own-aggregate-
score section rendering correctly with no closed episodes yet, an
already-frozen episode's goals staying locked while an un-frozen one
gets a real editable field, declaring leave, flagging a Team's interest
and confirming it flips the admin's highlight badge, approving one
pending request and denying another through the real popover form, and
reopening a frozen Goal Setting whose effect is confirmed from the
*manager's* page (the field becomes editable again) rather than just
trusting the reopen call didn't raise. Also verified with
`screenshot_associate_and_approvals.py` (same Playwright convention as
the other screenshot scripts) against the running server — all four "My
Journey" tabs, the interest flag toggling live, the admin's badge
lighting up, and the Approvals tab showing a real pending request. All
pre-existing suites (`smoke_test.py`, `test_bulk_import.py`,
`test_rotation_plan_bridge.py`, `test_admin_journey_ui.py`,
`test_manager_journey_ui.py`, and all `capabilities/*` pytest suites —
67+69+13+13+91 = 253 tests) still pass unchanged.

**Spec coverage after this phase**: every section of
`docs/associate_journey_redesign.md`'s Admin/Manager/Associate flows and
its cross-cutting rules table now has a corresponding screen. The only
items still explicitly out of scope are the ones the spec itself lists
under "Explicitly deferred / out of scope for this pass" — email/mail-
page deep-linking, resume file storage, and exact battery-bar rendering
past 2 years — none of which any phase was ever asked to build. Two
smaller, pre-existing "known MVP decisions to revisit" (real
notification dispatch/process orchestration for reminder timers, and
real auth) remain open platform questions tracked earlier in this
document, not new gaps introduced here.

### Resolved via scenario-based gap analysis (2026-09-12)

The following gaps were found by walking every role through every
lifecycle scenario, then fixed in the same pass — see
`capabilities/assignment/` (rules_config.py, service.py, domain.py,
adapters) and `apps/streamlit_ui/` for the changes:

- No `end_date >= start_date` validation → now enforced in
  `Assignment.__post_init__`.
- Extension could shorten an assignment → guard now requires
  `new_end_date` later than the current end (or start) date.
- Closure didn't require goal setting to exist → now a hard guard
  condition, with a clear error message.
- No bounds on `objective_score` → validated in `ClosureRecord.__post_init__`
  (0–5), not just the UI slider.
- Duplicate/overlapping Agent+Manager assignments were allowed → now
  rejected (`DuplicateAssignment`) unless the prior one is closed.
- No optimistic concurrency → `Assignment.version` + `ConcurrentModification`,
  enforced identically in both adapters (in-memory returns copies so a
  stale caller's write is actually detectable, matching SQL's WHERE-clause
  behavior).
- No "overdue closure" query → `list_overdue_closure` (repo + service +
  RBAC-scoped), defaulting to 2x the minimum-elapsed threshold.
- No early-termination path → `withdraw_assignment` (Manager-facing,
  unscored administrative closure).
- No manager-departure workflow → `reassign_all_from_departing_manager`
  (Functional-Owner-only, bulk close + reopen under a new manager).
- Manager-facing `swap_to_new_manager` conflated scoring with
  reassignment authority the spec gives to the central team → removed;
  see the note under block 2 above for the replacement flow.
- Reverse feedback had no time gate, unlike closure scoring → now gated
  by the same minimum-elapsed period.
- Two people with the same display name were indistinguishable in every
  picker → `party_helpers.disambiguate_labels` appends a short id suffix
  only on collision.
- No reserved field for a future external identity → `attributes["email"]`
  convention added to onboarding forms (see MVP decisions above — still
  a convention, not enforced).
- Unknown/corrupted `party_type` crashed the app → now caught, shows an
  error instead of a stack trace.
- "Switch person" had no safety valve at all → `ITAP_DEV_MODE` flag
  added (see MVP decisions above — still not a real security boundary).
- Raw technical exception text reached end users → RuleEngine's fallback
  message rewritten to be user-facing; most guard messages already were.

### Client deployment & setup data model (2026-09-12, associate-journey redesign, Phase 5)

Built the last section of `docs/associate_journey_redesign.md`, "Client
deployment & setup data model": moved the app from "seed demo data for a
look around" to a real, repeatable client-onboarding path — a fresh
deployment starts empty, and everything (including a full year of
rotation history for a demo) comes in through the same two upload
artifacts a real client would use: the Setup Workbook and an optional
`photos.zip`.

**Extended Setup Workbook schema (`apps/streamlit_ui/bulk_import.py`)**:

- `Managers` gained `team_name` — seeds the Teams catalog directly off
  this sheet (one Team per Manager, per the MVP "one-team-one-manager"
  resolution).
- `Associates` gained `photo_filename`, `bio`, `experience_summary`,
  `project_highlights`, `skills` (semicolon-separated), `interested_teams`,
  `interested_ccas` (semicolon-separated) — upserts the associate's
  `AssociateProfile`, self-declared `AssociateSkill`s, and `InterestFlag`s
  from `capabilities/catalog`.
- `Criteria Library` renamed to **`Skills`** and now feeds the *live*
  Skills catalog (`CatalogService.add_skill`), not a reference-only sheet
  — closing the gap Phase 1's "Not built in this pass" note called out.
- New **`CCA Activities`** sheet (`name`, `organizer_name`,
  `organizer_email`, `status`) seeds `CcaActivity` rows.
- `Assignments` gained `kind` (primary/secondary/cca, default primary)
  and three columns used only for an already-finished stint: `status`
  (active/closed), `objective_score`, `subjective_notes`. A row with
  `status=closed` is created (or, if matched, transitioned) **already
  closed and scored** — never "create open, leave it to be closed later."

**Constructing a closed historical Assignment — judgment call:**
`AssignmentService` was not given a new "create pre-closed" method.
Per this document's own architecture ("the service layer stays
permissive... this data-model layer stays permissive"), the existing
three-call sequence already supports it end to end with historical
dates: `create_assignment(start_date=..., end_date=...)` →
`record_goal_setting(...)` (if goals/criteria are present) →
`close_assignment(objective_score, subjective_notes, reason="completed",
as_of=end_date)`. The `as_of` parameter (already existed, used by
`guard_min_elapsed`) is what makes this work for a stint that ended long
ago — it evaluates the minimum-elapsed-days gate against the row's own
historical `end_date` rather than "today," so a 6-month-long stint from
last year closes cleanly in one import despite the live 30-day gate.
`bulk_import._apply_assignment_row` runs exactly this sequence; no
`assignment` service or domain change was needed.

**Upsert semantics — a real behavior change, not additive.** Every
`bulk_import.py` row previously matched-and-reused-unchanged for people
and skipped a duplicate Assignment outright; it now matches by natural
key and **updates the matched record's fields to whatever the file now
says**:

- People (Admins/Managers/Associates): matched by email first, else
  unambiguous exact name (unchanged); a match's `attributes` (function,
  email) are now upserted via `PartyRepo.update_attributes` rather than
  left untouched. **Judgment call**: `display_name` itself is never
  changed on a match — `PartyRepo.update_attributes` only merges
  `attributes`, there is no port method to rename a Party — adding one
  was judged not worth it for this pass since the natural key is email,
  not name; flagged in `bulk_import.py`'s own module docstring.
- Catalogs (Skills/Teams/CCA Activities): matched by name; a Team's
  manager or a CCA's organizer/status can be corrected on re-upload.
- Assignments: matched by associate + manager + kind + start_date. A
  still-ACTIVE match's `end_date`/goals/criteria are updated in place; a
  `status=closed` row against a still-active match actually closes it
  (the "upload once while ongoing, re-upload once finished" path). A
  match that is **already CLOSED** is left alone unless the new row is
  identical (reported as unchanged) — `ClosureRecord` is deliberately
  append-only (see "Known MVP decisions to revisit," `assignment`
  package) and this pass did not add an override path around that;
  correcting an already-imported score requires the admin's existing
  Approvals reopen action, not a re-import. Nothing is ever duplicated in
  either case — an unmatched row still creates a new record exactly as
  before. `test_bulk_import.py` covers both the create and the update
  path explicitly, including a re-upload with one changed field
  (a Manager's `function`, an Associate's `bio`, an Assignment's
  `end_date`) updating in place with no new row created.

**`photos.zip` (new, optional)**: `bulk_import.match_photos_to_associates`
matches each zip entry's filename against an Associates-sheet row's
`email` or `photo_filename` column (whole-filename or stem-only, so
`casey@example.com.jpg` and `casey.jpg` both work). **Judgment call on
storage**: `AssociateProfile.photo_url` is a plain `Optional[str]` with
no blob-storage adapter anywhere in this codebase, and `views/
associate_portfolio.py` already just calls `st.image(profile.photo_url)`
— which works identically for a URL or a local file path. Rather than
invent a new storage adapter, `photo_storage.py` writes the image to a
local directory (`$PHOTO_STORAGE_DIR`, default `./uploaded_photos`,
keyed by Agent id) and sets `photo_url` to that path — "follow the
existing shape" rather than add one. Revisit with a real object-storage
adapter if a deployment ever needs to run across multiple app instances
that don't share a filesystem.

**Upload audit log — new `catalog.domain.UploadAudit` /
`UploadKind`.** Lives in `capabilities/catalog` (its port/service/both
adapters), not a new capability: it is small, has no rule engine or
guarded state machine, and is squarely the same "admin-declared setup
data" rate of change as the rest of that package (see the Phase 1
"Catalog capability" note above for the fuller reasoning already applied
here). Append-only, same audit-integrity reasoning as
`assignment.ClosureRecord` — no update method. Records who uploaded
(admin party id + display name), when, what (`WORKBOOK`/`PHOTOS`), a
result summary (the same created/updated/reused/skipped/error counts the
Bulk Setup screen already showed), any row errors, and the **raw file
bytes** for traceability. `CatalogService.log_upload`/`list_uploads`
front it. **Where the read-only admin screen lives — judgment call**:
folded into the existing **Bulk Setup tab** (a "Past uploads (audit log)"
expander, right below the template download) rather than a new top-level
tab or folded into Setup — this is history *about* an upload action
taken on this exact tab, not admin-editable master data like
Skills/Teams/CCA (Setup's own scope), so it stays next to the action it
logs rather than living somewhere the admin would have to remember to
check separately.

**"Seed demo data" removed.** `app.py._seed_demo_data` and its welcome-
screen button are gone. In their place: `generate_demo_workbook.py`
builds an in-the-new-schema demo Setup Workbook on the fly (3 Admins, 6
Managers/Teams, 18 Associates, an 8-entry Skills catalog, 3 CCA
Activities, and — per spec's "a full year of rotation history if they
want to showcase one" — 2-3 closed-and-scored historical Primary stints
per Associate before their current still-open one), offered as a
`st.download_button` on the now-empty welcome screen. **Judgment call on
scale**: `HANDOVER_itap-platform.md` references an earlier
"4-admin/15-manager/40-associate" Bulk Setup sample, but that generator
script does not exist anywhere in this repo — only the mention survived.
Rather than fabricate a match to numbers with no surviving source,
`generate_demo_workbook.py`'s own docstring documents this and picks a
fresh, reasonably-scaled dataset in the same spirit (fast to import,
easy to look at, still shows real variety and a full year of history).
Downloading and then uploading it through Bulk Setup is the *only* path
to this data — there is no special seeding code in `app.py` anymore, per
spec ("trying the product and using it for real are the same code
path"). A brand-new deployment also had no way to create its first
Functional Owner at all once the seed button was removed (the existing
`home.py` "Add a new person" expander only had Associate/Manager forms)
— `home.py` gained a third "Create ITAP Admin" form alongside them,
closing that bootstrap gap.

**Console reset command**: `apps/streamlit_ui/reset_db.py` — drops and
recreates every table across all four capabilities this app wires up
(`party_identity`, `assignment`, `rotation_plan`, `catalog`), using each
package's own SQLAlchemy `metadata.drop_all`/`create_schema` rather than
raw `DROP TABLE` statements, so it can never drift from what each
package's adapter actually defines. Also clears the local photo storage
directory, since an orphaned photo file with no `AssociateProfile` row
pointing at it would otherwise survive a reset. Requires typing `yes` at
a confirmation prompt (or `--yes` / `RESET_DB_CONFIRM=yes` for scripted
use) — deliberately a separate command-line script, never a button
inside the app itself.

**Test coverage**: `capabilities/catalog` gained 6 new tests (the
`UploadAudit` repo contract, newest-first ordering, and the service's
`log_upload`/`list_uploads`) — 75 passing (was 69).
`apps/streamlit_ui/test_bulk_import.py` was rewritten for the new schema
and covers, in addition to the existing template-round-trip/missing-
column checks: creating people/Teams/Skills/CCAs/Assignments including a
historical closed-and-scored row in one pass, the associate profile/
self-declared-skills/interest-flags parsed straight from the template's
example row, a same-file re-upload creating nothing new, a re-upload
with one changed field (manager function / associate bio / assignment
end date) **updating** the matched record rather than skipping it, and
`photos.zip` matching by email and landing on disk. `smoke_test.py`,
`test_admin_journey_ui.py`, `test_manager_journey_ui.py`, and
`test_associate_and_approvals_ui.py` all previously bootstrapped their
fixture data by clicking the now-removed "Seed demo data" button; they
now call a small shared `test_fixtures.seed_basic_demo(services)` helper
directly against the service layer instead (same Casey/Dana/Alex/
Bailey/Priya fixture, including the cross-team-bifurcation Secondary),
since the app itself deliberately no longer has a seeding code path to
click through. All four suites, plus every `capabilities/*` pytest suite
(259 tests total) and `test_rotation_plan_bridge.py`, pass unchanged.

Verified end to end with Playwright (`screenshot_phase5.py`, same
convention as the other phase screenshot scripts) against a genuinely
empty database: the welcome screen with no seed button and a working
demo-dataset download, creating the first Admin through `home.py`'s new
form, the Bulk Setup tab's workbook + `photos.zip` uploaders and its
upload-audit-log expander, uploading and confirming the generated demo
workbook with zero row errors, and the Associates list actually showing
multi-segment tenure battery bars (several distinct-colored past-stint
segments per person) — confirming the "full year of rotation history,"
not just a few months, actually renders from a real upload rather than
only asserting it in a unit test.
