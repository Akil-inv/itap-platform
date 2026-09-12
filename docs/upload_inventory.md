# Upload File Inventory

Status: living reference. Generated from `apps/streamlit_ui/bulk_import.py`
directly — if this drifts from that file, the code is correct and this
needs updating in the same commit as whatever changed it.

Purpose: a single place to answer "which file, which sheet, which column
— and what does it actually become inside the app?" One workbook (the
**Setup Workbook**, `.xlsx`) plus one optional zip (**`photos.zip`**) are
the only two things a client ever uploads — see
`docs/associate_journey_redesign.md`'s "Client deployment & setup data
model" section for why it's deliberately just these two.

Both files are produced for you by the app itself, not hand-built from
scratch:
- **Setup Workbook, blank** — Bulk Setup tab → "Download template
  (.xlsx)" (`bulk_import.build_template_workbook()`), one example row per
  sheet.
- **Setup Workbook, full sample** — the empty-deployment welcome screen's
  "Download demo dataset" (`generate_demo_workbook.py`), a realistic
  full-year dataset.

## File 1: The Setup Workbook (`.xlsx`)

Six sheets. Every row is matched to an existing record by its **natural
key** and **upserted** (Phase 5) — re-uploading the same workbook with
one cell corrected updates that record; nothing is ever duplicated. See
each sheet's "Natural key" below.

### `Admins`

| Column | Required | Becomes |
|---|---|---|
| `name` | yes | `Party.display_name` (`party_type="functional_owner"`) |
| `email` | no | `Party.attributes["email"]` — also the natural key when present |

**Natural key**: email if given, else exact unambiguous name match.
**Shows up**: nowhere directly visible as data — this is who can sign in
as an ITAP Admin (the sign-in page's Admin list).

### `Managers`

| Column | Required | Becomes |
|---|---|---|
| `name` | yes | `Party.display_name` (`party_type="manager"`) |
| `email` | no | `Party.attributes["email"]` — natural key when present |
| `function` | no | `Party.attributes["function"]` — free-text grouping label (e.g. "Engineering") |
| `team_name` | no | Seeds a `catalog.Team` with this manager as its one manager (one-team-one-manager, MVP) |

**Natural key**: email if given, else exact unambiguous name match (same
rule as Admins/Associates).
**Shows up**: sign-in page's Manager list; `team_name` populates the
Setup tab's **Teams** catalog and is what an Associate's
`interested_teams` (below) has to match by name.

### `Associates`

| Column | Required | Becomes |
|---|---|---|
| `name` | yes | `Party.display_name` (`party_type="agent"`) |
| `email` | no | `Party.attributes["email"]` — natural key when present |
| `photo_filename` | no | Matched against an entry in `photos.zip` (see File 2) |
| `bio` | no | `AssociateProfile.bio` |
| `experience_summary` | no | One `ExperienceEntry` on `AssociateProfile.experience` (the sheet has no per-entry structure — one summary column becomes one entry) |
| `project_highlights` | no | Semicolon-split into one `ProjectHighlight` per item |
| `skills` | no | Semicolon-split; each name is upserted into the Skills catalog if new, then declared on this associate with `SkillSource.SELF` |
| `interested_teams` | no | Semicolon-split team names, each turned into an `InterestFlag` (`InterestTargetType.TEAM`) — must match an existing Team's name exactly (from `Managers.team_name`) or the row errors |
| `interested_ccas` | no | Same, against `InterestTargetType.CCA` — must match a `CCA Activities.name` |

**Natural key**: email if given, else exact unambiguous name match.
**Shows up**: sign-in page's Associate list; the Admin's Associates list
and Portfolio page (profile, skills-by-source, interest flags); the
Manager's read-only Profile tab; the Associate's own "My Journey" →
Profile tab (further editable there afterward).

### `Skills`

| Column | Required | Becomes |
|---|---|---|
| `name` | yes | `catalog.Skill.name` — natural key |
| `description` | no | `catalog.Skill.description` |

(Renamed from the old "Criteria Library" sheet — it now feeds the *live*
Skills catalog instead of sitting as a reference-only sheet.)
**Shows up**: Setup tab's **Skills** column; available for a Manager to
pick from during goal-setting; available for an Associate to self-add
against.

### `CCA Activities`

| Column | Required | Becomes |
|---|---|---|
| `name` | yes | `catalog.CcaActivity.name` — natural key |
| `organizer_name` | yes | Resolved against `Managers.name` → `CcaActivity.organizer_manager_id` |
| `organizer_email` | no | Only used to help resolve `organizer_name` if it's ambiguous |
| `status` | no | `open` or `closed` (defaults to `open`) → `CcaStatus` |

**Shows up**: Setup tab's **CCA activities** column; available for an
Associate's `interested_ccas` to reference; available as a `kind=cca`
row's target on the `Assignments` sheet (organizer becomes the CCA's
scorer).

### `Assignments`

| Column | Required | Becomes |
|---|---|---|
| `associate_name` | yes | Resolved against `Associates.name` |
| `manager_name` | yes | Resolved against `Managers.name` |
| `kind` | no (defaults `primary`) | `primary` \| `secondary` \| `cca` → `AssignmentKind` |
| `start_date` | yes | `Assignment.start_date` |
| `end_date` | no | `Assignment.end_date` |
| `goals` | no | `GoalSetting.goals`, recorded only while the assignment is still active |
| `criteria` | no | Semicolon-split → `GoalSetting.criteria` |
| `status` | no | Leave blank for a currently-open stint; set to `closed` for an already-finished historical one |
| `objective_score` | required **if** `status=closed` | `ClosureRecord.objective_score` |
| `subjective_notes` | no | `ClosureRecord.subjective_notes` |

**Natural key**: `associate_name` + `manager_name` + `kind` +
`start_date` together identify one stint. A matched **active** row's
`end_date`/`goals`/`criteria` get updated; a matched **active** row with
`status=closed` actually gets closed (with `end_date` as the closure
date) rather than left open. A matched row that's **already closed** is
left alone — `ClosureRecord` is append-only by design — unless the score
in the file now disagrees, in which case the row is reported as
`skipped` with a pointer to the admin's Approvals reopen action instead.

**This is the one sheet that carries a full year of history**: give it
many rows per associate — each one a separate finished, scored stint —
and the currently-open one last with no `end_date`/`status`.

**Shows up**: everywhere the Admin/Manager/Associate see rotation
history — the tenure battery bar (built from `kind=primary` rows only),
the Portfolio's rotation timeline and "N responsibilities" badge
(`secondary`/`cca` rows overlapping a primary stage), the hidden
aggregate score (average of every closed episode's score, any kind).

## File 2: `photos.zip` (optional)

One image file per associate. Matched against `Associates.photo_filename`
(whole-filename match first) or, failing that, against `Associates.email`
(stem match, so `casey@example.com.jpg` or `casey.jpg` both resolve to
`casey@example.com`). An unmatched zip entry is silently ignored; an
associate row with no matching entry just keeps whatever photo (or none)
it already had.

**Shows up**: everywhere a person's photo renders — list rows, the
Portfolio header, the Associate's own profile.

## What's tracked separately (not in either upload)

- **Upload audit log** (`catalog.UploadAudit`) — who uploaded which file,
  when, and the resulting created/updated/skipped/error counts. Visible
  in the Bulk Setup tab's "Past uploads" history. This is a record of the
  *uploads themselves*, not a second copy of the domain data.
- **Extension / Closure requests, goal freezes, review scores** — created
  by in-app manager/admin actions (Phases 3–4), never by the Setup
  Workbook. Re-importing an `Assignments` row never overrides a frozen
  goal or an already-submitted score — see the natural-key rules above.
