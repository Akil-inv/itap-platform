"""Setup/Configuration catalogs (Skills, Teams, CCA activities) plus the
small associate-declared records that reference them or sit alongside
them in the redesign's "Associate flow" (see
docs/associate_journey_redesign.md): self-declared/engagement-sourced
skills, the associate's own lean profile, standing interest flags, and
informational annual leave.

Built directly against ITAP's own vocabulary (Agent, Manager, Skill,
Team, CCA), same project decision as `capabilities/assignment/` — see
docs/architecture.md's "Decision" note. This package never imports
`assignment` or `party_identity`; Agent/Manager ids are opaque UUIDs
here, same by-id-only convention as `rotation_plan`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

# --- Setup catalogs -------------------------------------------------------


@dataclass
class Skill:
    """One entry in the shared, admin/manager-editable Skills catalog.
    Managers pick from this during goal-setting and add to it on the
    spot when what they need isn't there yet — no gatekeeping. Which
    specific Agent has which Skill, and whether it was self-declared or
    came from a scored engagement, is a separate record (AssociateSkill,
    below) — this class is only the catalog entry itself."""

    name: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("A skill needs a name")


class CcaStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass
class Team:
    """One entry in the Teams catalog. For MVP, one Team = one Manager
    (per the redesign spec's "resolved" note) — `manager_id` is required
    and singular. Nothing here stops two different Team rows from naming
    the same `manager_id`, which is deliberate: it leaves the door open
    for "a Manager oversees more than one Team" later without a schema
    change, even though the MVP build only ever creates one Team per
    Manager."""

    name: str
    manager_id: UUID
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("A team needs a name")


@dataclass
class CcaActivity:
    """One entry in the CCA (extra-curricular activity) catalog — a
    brownbag, a hackathon, anything outside the defined job scope that an
    Agent can flag standing interest in and later be scored against via a
    CCA-kind Assignment. `organizer_manager_id` is whoever
    organizes/scores it."""

    name: str
    organizer_manager_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: CcaStatus = CcaStatus.OPEN
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("A CCA activity needs a name")


# --- Associate-declared skills ---------------------------------------------


class SkillSource(str, Enum):
    SELF = "self"
    ENGAGEMENT = "engagement"


@dataclass
class AssociateSkill:
    """Links an Agent to a catalog Skill. Self-declared and
    manager/engagement-scored skills sit in the same list, distinguished
    only by this quiet `source` label (e.g. "self" vs "engagement") —
    never by a gate or approval flow (per spec: no verification system).
    `source_detail` carries the quiet label text itself (e.g. "Data Team
    engagement, Mar 2026") when source is ENGAGEMENT; left blank for a
    self-declared entry."""

    agent_id: UUID
    skill_id: UUID
    source: SkillSource
    id: UUID = field(default_factory=uuid4)
    source_detail: str = ""
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# --- Associate profile ------------------------------------------------------


@dataclass
class ExperienceEntry:
    """One prior-experience line on an associate's portfolio. Lean and
    structured — not a resume upload (explicitly out of scope, see the
    redesign spec's "Explicitly deferred" section)."""

    title: str
    description: str = ""
    start_date: date | None = None
    end_date: date | None = None


@dataclass
class ProjectHighlight:
    """One project-highlight line on an associate's portfolio."""

    title: str
    description: str = ""


@dataclass
class AssociateProfile:
    """The associate's own lean, structured portfolio: bio, prior
    experience, project highlights, photo. One per Agent (`agent_id` is
    the natural key — see AssociateProfileRepo.get/upsert). Sourced from
    the Excel upload wherever possible; the associate can edit it
    themselves at any time, it's never frozen for the duration of their
    stay (per spec)."""

    agent_id: UUID
    bio: str = ""
    photo_url: str | None = None
    experience: list[ExperienceEntry] = field(default_factory=list)
    project_highlights: list[ProjectHighlight] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# --- Interest signaling ------------------------------------------------------


class InterestTargetType(str, Enum):
    TEAM = "team"
    CCA = "cca"


@dataclass
class InterestFlag:
    """An Agent's standing interest in a Team or CCA activity from the
    Setup catalogs. Per spec: a general interest signal, never a request
    or preference to move, and admin-visible only — this record carries
    no workflow of its own. `active=False` records that the Agent later
    unflagged it, kept rather than deleted so the history isn't lost."""

    agent_id: UUID
    target_type: InterestTargetType
    target_id: UUID
    id: UUID = field(default_factory=uuid4)
    active: bool = True
    flagged_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class InterestActivity:
    """Per-Agent marker the admin's associate list uses to decide whether
    to show the "interest changed" highlight badge: `raised_at` moves
    forward every time any of the Agent's InterestFlags changes (a new
    flag, or one flipped off); `seen_at` moves forward when the admin
    opens that Agent's profile. The badge shows exactly when
    `raised_at` is newer than `seen_at` — see
    CatalogService.has_unseen_interest_change."""

    agent_id: UUID
    raised_at: datetime | None = None
    seen_at: datetime | None = None


# --- Annual leave ------------------------------------------------------------


@dataclass
class AnnualLeave:
    """A single declared leave date-range for an Agent. Purely
    informational (per spec: no approval workflow) — manager/admin
    planning visibility only."""

    agent_id: UUID
    start_date: date
    end_date: date
    id: UUID = field(default_factory=uuid4)
    note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.end_date < self.start_date:
            raise ValueError(
                f"end_date ({self.end_date}) cannot be before start_date ({self.start_date})"
            )


# --- Errors -------------------------------------------------------------------


# --- Upload audit log (Phase 5, client deployment & setup) --------------------


class UploadKind(str, Enum):
    """What was uploaded through the Bulk Setup screen. WORKBOOK is the
    Setup Workbook (.xlsx); PHOTOS is the optional photos.zip — see
    docs/associate_journey_redesign.md's "Client deployment & setup data
    model" section."""

    WORKBOOK = "workbook"
    PHOTOS = "photos"


@dataclass
class UploadAudit:
    """A record of one Bulk Setup upload — who, when, what, and a result
    summary — kept separate from the live data (which stays upserted, one
    current truth) per spec: "history for the setup files themselves,"
    not version history of the domain data. The raw file bytes are
    retained for traceability (re-download exactly what was uploaded).
    Append-only: there is no update method, matching the same
    audit-integrity reasoning as `assignment.ClosureRecord`."""

    uploaded_by_name: str
    kind: UploadKind
    filename: str
    id: UUID = field(default_factory=uuid4)
    uploaded_by: UUID | None = None
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    summary: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    raw_file: bytes = b""


class SkillNotFound(Exception):
    def __init__(self, skill_id: UUID):
        super().__init__(f"Skill {skill_id} not found")
        self.skill_id = skill_id


class TeamNotFound(Exception):
    def __init__(self, team_id: UUID):
        super().__init__(f"Team {team_id} not found")
        self.team_id = team_id


class CcaActivityNotFound(Exception):
    def __init__(self, cca_id: UUID):
        super().__init__(f"CCA activity {cca_id} not found")
        self.cca_id = cca_id
