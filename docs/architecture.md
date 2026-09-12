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
   overdue-closure queries for a future reminder job. 55 tests passing
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
