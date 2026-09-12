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
from typing import Optional
from uuid import UUID, uuid4


class AssignmentState(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


@dataclass
class Assignment:
    """An Agent placed under a Manager for a period. One Agent may hold
    multiple concurrent Assignments (cross-team bifurcation) — each is an
    independent record scored only by its own Manager."""

    agent_id: UUID
    manager_id: UUID
    start_date: date
    id: UUID = field(default_factory=uuid4)
    end_date: Optional[date] = None
    state: AssignmentState = AssignmentState.ACTIVE
    closed_reason: Optional[str] = None  # "completed" | "swapped"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GoalSetting:
    """Recorded once manager and agent agree on goals for an Assignment.
    Not a gate on the Assignment starting — but its absence is queryable
    so the system can remind the manager (see AssignmentRepo.
    list_active_without_goal_setting)."""

    assignment_id: UUID
    goals: str
    id: UUID = field(default_factory=uuid4)
    set_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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


@dataclass(frozen=True)
class ReverseFeedback:
    """Agent's feedback about the Manager they worked under. Immutable for
    the same reason as ClosureRecord. Gated only by the minimum-elapsed
    rule, not by Assignment state — can be given before or after closure."""

    assignment_id: UUID
    notes: str
    id: UUID = field(default_factory=uuid4)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AssignmentNotFound(Exception):
    def __init__(self, assignment_id: UUID):
        super().__init__(f"Assignment {assignment_id} not found")
        self.assignment_id = assignment_id
