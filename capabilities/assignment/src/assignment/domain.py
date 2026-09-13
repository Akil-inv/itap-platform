"""ITAP assignment lifecycle — domain model.

Built directly against ITAP's own vocabulary (Agent, Manager) rather than
generic Subject/Holder naming — per the project decision to prioritize a
working platform over premature genericity. If a second, unrelated use
case needs this later, extract and rename then; don't guess now.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

MIN_OBJECTIVE_SCORE = 0.0
MAX_OBJECTIVE_SCORE = 5.0


class AssignmentState(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class AssignmentKind(str, Enum):
    """Same underlying record, three display names depending on whose
    screen it's on (Associate: Episode, Manager: Engagement, Admin:
    Assignment — see docs/associate_journey_redesign.md). `kind` is what
    actually varies:

    - PRIMARY: the Agent's main team assignment. Per the spec, exactly
      one should be active at a time — this data-model layer stores the
      value but does not itself enforce that invariant (see
      AssignmentService.create_assignment for why).
    - SECONDARY: a real, concurrent assignment under a *different*
      Manager while a Primary is also active — this is what the existing
      cross-team bifurcation capability produces going forward. Same
      shape as a Primary: own manager, dates, goals, score.
    - CCA: an extra-curricular activity (organizing a brownbag, a
      hackathon, ...), event-based, tagged to whichever manager/organizer
      scores it. Can occur alongside an active Primary or during an
      Available/Unassigned gap between Primary stages.

    Defaults to PRIMARY so every Assignment created before this field
    existed (and every call site that doesn't care) keeps its original
    meaning.
    """

    PRIMARY = "primary"
    SECONDARY = "secondary"
    CCA = "cca"


# closed_reason values:
#   "completed"        - normal tenure completion, scored via ClosureRecord
#   "withdrawn"         - Agent left early; no score, see closure_note
#   "manager_departed"  - Manager left; Agent reassigned, see closure_note
CLOSED_REASONS = {"completed", "withdrawn", "manager_departed"}


@dataclass
class Assignment:
    """An Agent placed under a Manager for a period. One Agent may hold
    multiple concurrent Assignments — one Primary plus any number of
    Secondary/CCA (cross-team bifurcation is the Secondary case) — each
    an independent record scored only by its own Manager/organizer.

    `version` is used for optimistic concurrency: every persisted update
    must supply the version it read, and adapters must reject (raise
    ConcurrentModification) a write against a version that has since
    moved — see AssignmentRepo.update / close_with_record.
    """

    agent_id: UUID
    manager_id: UUID
    start_date: date
    id: UUID = field(default_factory=uuid4)
    end_date: date | None = None
    state: AssignmentState = AssignmentState.ACTIVE
    kind: AssignmentKind = AssignmentKind.PRIMARY
    closed_reason: str | None = None
    closure_note: str | None = None
    version: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError(
                f"end_date ({self.end_date}) cannot be before start_date ({self.start_date})"
            )


@dataclass
class GoalSetting:
    """Recorded once manager and agent agree on goals for an Assignment.
    Not a gate on the Assignment starting — but its absence is queryable
    so the system can remind the manager (see AssignmentRepo.
    list_active_without_goal_setting), and it IS required before closure
    (see AssignmentService.close_assignment) — closing without it would
    mean scoring against goals that were never set.

    `criteria` is an optional structured checklist (e.g. ["Communication",
    "Technical Skill", "Ownership"]) — a lightweight rubric to assess
    against at closure. Deliberately not a separate per-criterion score:
    closure still records one objective_score + subjective_notes; criteria
    just make explicit *what* that score should be judged against.

    **Freeze/agree pattern (2026-09-12, associate-journey redesign, Phase
    3):** per docs/associate_journey_redesign.md's "Goals tab" — the
    manager and associate agree on goals verbally, offline; the goal text
    is keyed in (editable up to this point, an upsert via
    AssignmentService.record_goal_setting), and the manager's **Agree &
    Freeze** action (AssignmentService.freeze_goal_setting) sets `frozen`,
    `agreed_by` (the manager's party id) and `agreed_at`. Once frozen,
    neither side may edit it — only an admin-opened window
    (AssignmentService.reopen_goal_setting) clears the freeze again."""

    assignment_id: UUID
    goals: str
    id: UUID = field(default_factory=uuid4)
    criteria: list[str] = field(default_factory=list)
    set_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    frozen: bool = False
    agreed_by: UUID | None = None
    agreed_at: datetime | None = None


@dataclass(frozen=True)
class ClosureRecord:
    """Manager's assessment of the Agent at Assignment closure. Immutable
    once created — corrections require a new Assignment cycle, not an
    edit, so the record stays trustworthy for dispute resolution."""

    assignment_id: UUID
    objective_score: float
    subjective_notes: str
    id: UUID = field(default_factory=uuid4)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not (MIN_OBJECTIVE_SCORE <= self.objective_score <= MAX_OBJECTIVE_SCORE):
            raise ValueError(
                f"objective_score must be between {MIN_OBJECTIVE_SCORE} and "
                f"{MAX_OBJECTIVE_SCORE}, got {self.objective_score}"
            )


@dataclass
class ReviewScore:
    """Manager's Review & Scoring submission for an Assignment that is
    still ACTIVE — distinct from ClosureRecord, which is only ever
    written at the moment an Assignment actually transitions to CLOSED
    (docs/associate_journey_redesign.md's "Review & Scoring tab": the
    manager submits scores directly, no admin gate on *scoring* itself,
    but the associated Assignment isn't closed until a separate Closure
    *request* is later approved by an admin — see ChangeRequest below).

    `criterion_scores` maps each of GoalSetting.criteria's entries to a
    0-5 score; `objective_score` is the simple average across them (per
    spec: "simple average — no weighting unless we decide otherwise
    later"), computed by AssignmentService.submit_review_score rather
    than entered directly, so the UI can't drift from "average of the
    criteria" on its own. If no criteria were recorded, `criterion_scores`
    may be a single ad-hoc entry (e.g. {"Overall": 4.0}) — still averaged
    the same way, so there's exactly one code path.

    Frozen immediately on submission, same override pattern as
    GoalSetting: only AssignmentService.reopen_review_score (admin) clears
    `frozen` so the manager can correct and resubmit."""

    assignment_id: UUID
    criterion_scores: dict[str, float]
    objective_score: float
    notes: str = ""
    id: UUID = field(default_factory=uuid4)
    submitted_by: UUID | None = None
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    frozen: bool = True

    def __post_init__(self) -> None:
        if not self.criterion_scores:
            raise ValueError("At least one criterion score is required")
        for name, value in self.criterion_scores.items():
            if not (MIN_OBJECTIVE_SCORE <= value <= MAX_OBJECTIVE_SCORE):
                raise ValueError(
                    f"Score for {name!r} must be between {MIN_OBJECTIVE_SCORE} and "
                    f"{MAX_OBJECTIVE_SCORE}, got {value}"
                )


class RequestType(str, Enum):
    EXTENSION = "extension"
    CLOSURE = "closure"


class RequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


@dataclass
class ChangeRequest:
    """The manager-requests / admin-approves pattern
    (docs/associate_journey_redesign.md's "Extension / Closure / Withdraw"
    section) for the two Assignment actions that are NOT direct manager
    actions, unlike Withdraw. Deliberately its own small record rather
    than reusing the existing (direct, no-approval) `request_extension`/
    `close_assignment` service calls — those keep their current behavior
    unchanged for whatever already depends on them; this is a genuinely
    new gated path.

    `new_end_date` is set only for an EXTENSION request. Approving a
    CLOSURE request is what actually calls `close_assignment` (using the
    Assignment's already-submitted, frozen ReviewScore) and is what moves
    the Agent into the Available pool per spec — not the request itself.

    **Admin-approval UI is not built in this pass** — see
    AssignmentService.approve_change_request/deny_change_request below
    and docs/architecture.md's Phase 3 section. This dataclass and the
    service methods around it are the request-creation half only."""

    assignment_id: UUID
    request_type: RequestType
    requested_by: UUID
    id: UUID = field(default_factory=uuid4)
    new_end_date: date | None = None
    notes: str = ""
    status: RequestStatus = RequestStatus.PENDING
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_by: UUID | None = None
    decided_at: datetime | None = None


class GoalSettingFrozen(Exception):
    """Raised when an edit or freeze is attempted against a GoalSetting
    that is already frozen — only AssignmentService.reopen_goal_setting
    (admin) can clear this."""


class ReviewScoreFrozen(Exception):
    """Raised when a re-submission is attempted against a ReviewScore
    that is already frozen — only AssignmentService.reopen_review_score
    (admin) can clear this."""


class ChangeRequestNotFound(Exception):
    def __init__(self, request_id: UUID):
        super().__init__(f"ChangeRequest {request_id} not found")
        self.request_id = request_id


@dataclass(frozen=True)
class ReverseFeedback:
    """Agent's feedback about the Manager they worked under. Immutable for
    the same reason as ClosureRecord. Gated by the same minimum-elapsed
    rule as closure (see AssignmentService.record_reverse_feedback) —
    not by Assignment state, so it can be given before or after
    closure."""

    assignment_id: UUID
    notes: str
    id: UUID = field(default_factory=uuid4)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AssignmentNotFound(Exception):
    def __init__(self, assignment_id: UUID):
        super().__init__(f"Assignment {assignment_id} not found")
        self.assignment_id = assignment_id


class ConcurrentModification(Exception):
    """Raised when a write is attempted against a stale Assignment version
    — someone else (another tab, another user) updated it first."""

    def __init__(self, assignment_id: UUID):
        super().__init__(
            f"Assignment {assignment_id} was modified by someone else — reload and retry."
        )
        self.assignment_id = assignment_id


class DuplicateAssignment(Exception):
    """Raised when creating an Assignment that would duplicate an existing
    active Assignment for the same Agent/Manager pair."""

    def __init__(self, agent_id: UUID, manager_id: UUID):
        super().__init__(
            f"Agent {agent_id} already has an active assignment with manager {manager_id}"
        )
        self.agent_id = agent_id
        self.manager_id = manager_id
