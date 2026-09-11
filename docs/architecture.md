# ITAP Architecture

Status: Living document. Update this alongside code changes — it is not a
one-time design note. Whenever a capability's port, adapter set, or cutoff
rationale changes, update the corresponding row below in the same commit.

## Purpose

ITAP (Intern Training & Assignment Platform) is the first real workload
built against a **capability catalog**: a set of domain-agnostic building
blocks that are meant to be reused, unmodified at the core, across future
solutions (a work-order assignment system, a ticket assignment system, etc.)
by supplying different configuration rather than different code.

If ITAP-specific vocabulary ever leaks into a capability block's core code,
that is a defect in the cutoff, not an acceptable shortcut.

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

1. **Party/Identity** (this slice) — foundational, every other block
   depends on it.
2. **Assignment Engine + Rule Engine** — the core state machine, testable
   headlessly with an in-memory Party repo.
3. **RBAC Scope** — layered over 1 and 2 once both are stable.
4. **Scoring & Closure**, **Notification Dispatch**, **Process
   Orchestration** — in parallel once the core loop is proven.
5. **Outbox/Event Sync** — added once the CML platform questions above are
   answered.
