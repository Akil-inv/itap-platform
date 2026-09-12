# ITAP Redesign: Associate-Centric Journey

Status: Design spec, frozen by discussion, not yet built. This is the
single source of truth for the redesign — check every mockup and every
line of implementation against it. Update it in the same commit as any
decision that changes it; don't let it drift out of sync with the mockup
or the code the way a chat thread would.

## Why this redesign

The current app is organized by **role** (Functional Owner tab, Manager
tab, Associate tab), which scatters one person's lifecycle across
disconnected screens: onboarding is one form, goal-setting another,
closing an assignment another, rotation planning yet another. The
redesign organizes around the **associate's journey** instead — one
person, one timeline, one page — and treats role-based permissions as a
filter on top of that, not the primary navigation.

## Core entities

### Episode / Engagement / Assignment — one entity, three names

The same underlying record is called a different thing depending on
whose screen it's shown on:

| Viewpoint | Name used |
|---|---|
| Associate | **Episode** |
| Manager | **Engagement** |
| Admin | **Assignment** |

This is display-language only (same pattern as the existing
`role_labels.py` convention) — the domain model has one entity, not
three.

Every one of these records has a **`kind`**:

- **Primary** — the associate's main team assignment. Exactly one is
  active at a time. This is the spine that drives the rotation curve
  and the tenure battery bar.
- **Secondary** — a real, concurrent assignment under a *different*
  manager while a Primary is also active (the existing cross-team
  bifurcation capability). Has its own manager, dates, goals, and score,
  same as a Primary.
- **CCA** (extra-curricular activity — organizing a brownbag, a
  hackathon, anything outside the defined job scope) — event-based,
  tagged to whichever manager/organizer scores it. Can occur while a
  Primary is active, or during an Available/Unassigned gap between
  Primary stages.

Every kind carries its own score, submitted by whoever manages that
specific responsibility.

### Available / Unassigned

The state an associate sits in between a closed Primary and the next
one being allocated. Not idle — CCAs can still happen during this
window. The tenure battery bar keeps counting through it (as a neutral
segment); what actually matters to the admin during this window is how
many responsibilities the associate handled and how they scored, not
"are they doing nothing."

### Responsibilities rollup

For any given Primary stage (or an Available gap), the admin/manager
view surfaces an **"N responsibilities" count** — the Primary itself
(if any) plus every Secondary and CCA that overlapped that window —
each expandable to its own manager, dates, and score. The associate's
one aggregate score is the average across **all** episodes of all kinds,
all-time (simple average — no weighting of Primary over Secondary/CCA
unless we decide otherwise later).

**Overlap rule**: if a Secondary or CCA's dates span two Primary stages,
anchor it to whichever Primary stage was active on its *start date*, and
show a "continues into next stage" note rather than splitting it across
both.

### Skills

A shared, admin/manager-editable catalog (part of Setup, below).
Managers pick from it during goal-setting; if what they need isn't
there, they add it on the spot — no gatekeeping, no approval step. An
associate can also self-declare skills/certifications on their own
profile (e.g., "attended an internal training") with **no verification
system** — self-declared and manager-scored skills sit in the same list,
distinguished only by a quiet source label (e.g., "from Data Team
engagement, Mar 2026" vs. "self-added"), never by a gate or approval
flow.

### Teams and CCA catalog (Setup)

Both are admin-maintained master data, seeded from the Excel upload and
also addable directly in the UI — same pattern as the Skills catalog.
These, together with Skills, live in a distinct **Setup/Configuration**
area of the app (not mixed into daily operational screens), and are the
kind of thing an admin configures once when standing up the platform
and revisits occasionally, not something touched per-associate.

**Resolved**: for MVP, one Team = one Manager — "Team" is effectively
the manager's own `function` tag, not a separate finer-grained catalog
nested under it. The data model should still allow a manager to be
tagged to more than one team in the future (a manager overseeing
multiple teams) — worth keeping the door open in the schema — but the
MVP build and mockup only need to support the one-team-one-manager
case.

## Admin flow

### Associates list (entry point)

Populated from the Excel bulk upload (manager, function, photo per
row). Each row ("ribbon") shows:

- Associate name (click → opens their portfolio)
- Current team/manager
- **Tenure battery bar**: 1 bar = 3 months of *total time in the
  system* (not just the current team). Green = current manager's
  stint; each **past** stint gets its own distinct color, so the whole
  bar reads as a compressed, stacked history of every episode this
  person has had. An Available/gap stretch renders as a neutral
  segment. The bar keeps growing past 8 segments (2 years) rather than
  capping — exact rendering for 3+ years TBD at mockup time.
- **Hidden aggregate score**: never shown inline. An eye icon reveals
  it on click, then it hides again — a bank-balance interaction, not a
  flashed number. A full-list export (with scores visible) is
  available for whoever's authorized to pull a bulk performance report.
- **Interest-change highlight**: if the associate has recently changed
  their team/CCA interest flags, the row carries a highlight/badge.
  Opening the profile is what clears it (a "seen it" pattern).
- Filters/tabs for status (Active / Needs attention / Available /
  Completed, etc. — exact set TBD at mockup time).

A single-person onboarding form stays available as a back door for
one-off additions between Excel uploads; Excel remains the *preferred*
path for bulk onboarding (including manager/function/photo/profile
fields wherever the sheet can carry them).

### Associate portfolio (level 2)

Reached by clicking a name. Shows:

- Photo, lean structured profile (bio, prior experience entries,
  skills — pulled from the shared catalog plus self-added — project
  highlights). Sourced from Excel wherever possible; associate can also
  edit their own profile anytime, it's never frozen for the duration of
  their stay.
- Current assignment + the rotation curve (built from the Primary
  spine).
- Each Primary stage card shows its "N responsibilities" badge
  (Secondary/CCA overlays), expandable to level 3 detail.
- Team/CCA interest flags the associate has declared (standing
  signals, not a request to move — see "Interest signaling" below).
- Actions: close current Primary and advance to the next stage
  (in-place, one guided step — see the mockup), add a Secondary
  (concurrent real assignment, own manager), log a CCA.

### Engagement detail (level 3)

Reached from a Primary stage or from expanding its responsibilities
badge: the individual scores against goal-setting criteria/skills for
that one episode, rolled into its one episode score. Both level 2 and
level 3 need PDF export/print.

### Setup / Configuration

A distinct area (not mixed into daily screens) holding:

- **Skills catalog** — reusable, anyone (manager) can extend during
  goal-setting.
- **Teams catalog** — seeded from Excel, addable via UI.
- **CCA catalog** — seeded from Excel, addable via UI (the list of
  currently open/available extracurricular opportunities associates can
  flag interest in).

These are the kind of thing an admin walks through as setup steps when
first standing up the platform for real use, and revisits occasionally
afterward.

## Manager flow

### Associates list (scoped to the manager)

Same shape as the admin's list, filtered to the manager's own team.
Two tabs:

- **Current** — associates presently assigned to this manager.
- **Rolled Off** — associates who've since moved to a different
  manager; read-only history of the relationship, retained indefinitely.

Battery bar visible. **Aggregate score is never visible to a manager**
— for anyone but themselves (see below) or the associate's own view.

### Associate profile (level 2, manager's view)

Same lean structured profile as the admin sees (read from Excel).

#### Goals tab

The manager and associate agree on goals **verbally, offline**. The
associate then keys the agreed goals into the system; the manager
clicks **Agree**, which **freezes** the goal for both parties — neither
the associate nor the manager can edit it afterward. If the manager
later wants to add a new project to the measurement mid-engagement, an
**admin must open the window** first; there's no self-service edit path
around the freeze for either side.

#### Review & Scoring tab

The manager submits scores directly — no admin gate on this step. Once
submitted, the score is frozen; the manager can see the score they
gave, but correcting it requires the admin to reopen it, after which
the manager edits and resubmits. Same freeze/override pattern as goals,
applied to scores.

#### Extension / Closure / Withdraw

- **Extension**: the manager clicks to request it; the admin approves;
  logged (auditable request/approval pair).
- **Closure**: after scoring, the manager requests closure (i.e., "I'm
  done, please roll this person off my team"); the admin approves,
  which is what actually moves the associate into the Available pool;
  logged the same way as Extension.
- **Withdraw**: stays a **direct** manager action, no admin approval —
  for early/exceptional exits from a rotation or the program.

## Associate flow

The simplest of the three — mostly self-service and read access to
their own history.

- **Profile**: fully self-editable at any time (not frozen for the
  duration of their stay) — add certifications and new skills as they
  go, update their own photo. Admin can also update the photo on their
  behalf if they're slow to do it themselves.
- **Current assignment**: this is where the associate fills in proposed
  goals for the active engagement (per the manager's Goals tab flow
  above) and sees them once the manager agrees and freezes them.
- **History**: their own past episodes, read-only.
- **Own aggregate score**: visible to the owning associate only (never
  to other associates) — so they can tell whether their trend is
  helping or hurting their overall number. Individual past episode
  scores are also visible to them as milestones along their own
  learning curve.
- **Rotation plan preview**: if a plan exists for them, they can see
  when they're due to move next; if no plan exists, there's simply
  nothing to show there yet.
- **Annual leave**: purely informational — the associate declares
  dates for manager/admin planning purposes. **No approval workflow.**
- **Interest signaling**: an associate can flag standing interest in
  specific Teams and/or CCAs from the Setup catalogs. This is a
  **general interest signal, not a request or preference to move** —
  the UI must not imply that flagging interest lets them choose their
  next placement. If the admin wants to act on a flagged interest
  (e.g., loop a manager in about a secondary responsibility), that's a
  conversation that happens outside the system between the admin and
  the relevant managers; the system only surfaces the signal, it never
  executes a placement from it. Any change to an associate's flagged
  interests raises the highlight on the admin's list (above).

## Cross-cutting rules (reference table)

| Rule | Detail |
|---|---|
| Tenure battery bar | 1 bar = 3 months of total time in the system. Green = current manager stint. Each past stint its own color. Available/gap periods = neutral segment, clock keeps running. |
| Aggregate score visibility | Admin: hidden behind an eye-icon reveal (+ full-list export). Manager: never visible for others; visible for scores they personally gave. Associate: visible for their own aggregate + their own per-episode milestones. Never visible to other associates. |
| Freeze / override pattern | Goals: frozen once the manager agrees; locked for both parties; only an admin-opened window allows a later change. Scores: frozen once the manager submits; only an admin reopen allows a correction. |
| Request / approve / log pattern | Extension: manager requests → admin approves → logged. Closure: manager requests (after scoring) → admin approves → associate moves to Available → logged. |
| Direct, no-approval actions | Withdraw (manager, any time, no admin gate). Profile edits, skill additions, annual leave declarations, interest flags (associate, any time, no approval). |
| Responsibilities rollup | Per Primary stage (or Available gap): count of concurrent Secondary/CCA + the Primary itself, each independently scored, each expandable to detail. Aggregate score = simple average across all episodes of all kinds, all-time. |
| Skills | Shared catalog, freely extended by managers during goal-setting; associates can self-declare without verification; source (self vs. scored-engagement) shown as a quiet label only. |
| Teams / CCA catalog | Admin-maintained master data (Setup area), seeded from Excel, addable via UI. |

## Explicitly deferred / out of scope for this pass

- **Email/"mail page" deep-linking** into an associate's episode ribbon
  — a future feature, not designed yet.
- **Resume file storage** — decided against in favor of the lean
  structured profile described above; revisit only if a real need for
  actual uploaded resume documents (as opposed to structured fields)
  shows up later.
- **Exact battery-bar rendering past 2 years (9+ segments)** — left to
  the mockup pass.
- **A manager overseeing more than one team** — not MVP (see "Teams and
  CCA catalog" above), but keep the schema open to it for later.

## Sequencing

1. **This document** — frozen reference for the model (this file).
2. **Mockup pass** — freeze the look and feel across all three roles
   plus Setup, working from this spec, before any core/data-model work
   starts.
3. **Wire to core** — once the mockup is approved, work out the actual
   data-model changes (new `kind` field on assignments, Teams/CCA/Skills
   catalog tables, interest-flag records, profile fields, leave
   records) and migration path from the current role-tab app.
4. **Build.**
