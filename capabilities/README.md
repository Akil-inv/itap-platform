# Capability catalog

Each subdirectory here is one domain-agnostic capability block from
`docs/architecture.md`. Conventions, applied to every block:

- Independently installable Python package (`pyproject.toml`, `src/` layout).
- No dependency on any other capability's concrete adapters — only on
  another capability's **port** (interface), if at all.
- No domain-specific vocabulary (no "Intern", "Ticket", "Work Order", ...)
  anywhere in `src/`. Domain vocabulary is supplied by the consuming
  application as configuration or as arguments at call time.
- A `ports.py` defining the interface(s) the block exposes.
- An `adapters/` package with at least one reference implementation
  (usually `in_memory.py`, used in the contract test suite and by any
  other block's tests that depend on this one).
- A contract test suite (`tests/test_*_contract.py`) that runs against
  every adapter via a pytest fixture parametrized by adapter — new
  adapters must pass the same suite, unmodified, to be considered correct.

## Blocks

| # | Directory | Status |
|---|---|---|
| 1 | `party_identity/` | Scaffolded — domain model, `PartyRepo` port, in-memory + SQL adapters, contract tests passing |
| 2/3 | `assignment/` | Built directly for ITAP (assignment lifecycle + rule-guarded transitions + goal setting + closure scoring + reverse feedback + administrative closure paths + optimistic concurrency), 59 tests passing across in-memory + SQL adapters. Not yet generalized — see note below. |
| 4 | process orchestration | Deferred — no timer/reminder dispatch yet; `list_overdue_goal_setting` and `list_overdue_closure` exist as the queries a future job would poll |
| 5 | scoring & closure | Folded into `assignment/` for now (ClosureRecord, ReverseFeedback) |
| 6 | `rbac_scope/` | Built — `ScopedAssignmentQueries`: 3-way visibility (Functional Owner / Manager / Agent) computed from relationship to the record, not per-role queries. 13 tests passing. Depends on `assignment` at runtime (see its README for install). |
| 7 | notification dispatch | Not started |
| 8 | outbox sync | Not started |
| — | `rotation_plan/` | Built — `RotationPlanService`: a fixed, named path of stages (e.g. "Platform Team" -> "Data Team" -> "Product Team") an Agent is enrolled into, with a computed fractional position along it (`progress_value`) for the "you are here" journey-curve UI. `Enrollment.stage_assignments` links a stage index to the `assignment.Assignment` id covering it; `RotationPlan.default_stage_managers` optionally names the Manager who should get a new Assignment automatically when a stage is reached. Both by id only — this package still never imports `assignment` or `party_identity`, per the no-concrete-cross-capability-dependency convention. 91 tests passing across in-memory + SQL adapters. |

**Note on genericity:** per project decision (2026-09-12), we're prioritizing
a working ITAP platform over premature generalization. `assignment/` is
built directly against ITAP's own vocabulary (Agent/Manager), not generic
Subject/Holder naming — see `docs/architecture.md` for the full rationale.
Extract and generalize a block only once a second, real use case needs it.

See `docs/architecture.md` for what each block owns and why the boundary
is drawn where it is.
