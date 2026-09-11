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
- Architecture established and documented in `docs/architecture.md`:
  ITAP is built as configuration over an 8-block, domain-agnostic
  capability catalog (`capabilities/`), so each block is reusable in
  future, unrelated solutions.
- Capability block 1, **Party/Identity**, scaffolded in
  `capabilities/party_identity/`: domain model, `PartyRepo` port,
  in-memory adapter, SQL adapter (SQLAlchemy Core, Postgres/SQLite
  portable). 13 contract tests passing against both adapters.

### In Progress

- Capability block 2 (Assignment Engine) and block 3 (Rule/Decision
  Engine) — next build slice.

### Next

- Build Assignment Engine + Rule Engine as the core testable state
  machine (in-process YAML-driven rule adapter first; Drools/Flowable
  are candidate future adapters behind the same ports, not required for
  the first working slice).
- Then RBAC Scope, layered over blocks 1-2 once both are stable.

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
