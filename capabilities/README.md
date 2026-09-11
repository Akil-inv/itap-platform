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
| 2 | `assignment_engine/` | Not started |
| 3 | `rule_engine/` | Not started |
| 4 | `process_orchestration/` | Not started |
| 5 | `scoring_closure/` | Not started |
| 6 | `rbac_scope/` | Not started |
| 7 | `notification_dispatch/` | Not started |
| 8 | `outbox_sync/` | Not started |

See `docs/architecture.md` for what each block owns and why the boundary
is drawn where it is.
