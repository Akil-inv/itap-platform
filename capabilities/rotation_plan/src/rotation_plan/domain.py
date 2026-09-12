"""A rotation plan is a fixed, named path of stages (e.g. "Platform Team"
-> "Data Team" -> "Product Team") that an Agent is enrolled into, so their
next placement isn't a one-off decision each time. A stage is a
label/track, not a specific Manager — `Enrollment.stage_assignments` maps
a stage index to the `assignment.Assignment` id that actually covers it,
by id only: this package never imports `assignment` (no dependency on
another capability's concrete types, per docs/architecture.md's
capability conventions) — the caller (the Streamlit app layer, which
already talks to both capabilities) is what resolves an id to a Manager
name or dates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass
class RotationPlan:
    name: str
    stage_names: list[str]
    id: UUID = field(default_factory=uuid4)
    weeks_per_stage: int = 8
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("A rotation plan needs a name")
        if len(self.stage_names) < 2:
            raise ValueError("A rotation plan needs at least 2 stages")
        if any(not s.strip() for s in self.stage_names):
            raise ValueError("Stage names can't be blank")
        if self.weeks_per_stage < 1:
            raise ValueError("weeks_per_stage must be at least 1")

    @property
    def stage_count(self) -> int:
        return len(self.stage_names)


@dataclass
class Enrollment:
    plan_id: UUID
    agent_id: UUID
    id: UUID = field(default_factory=uuid4)
    current_stage_index: int = 0
    enrolled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stage_started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stage_assignments: dict[int, UUID] = field(default_factory=dict)
    version: int = 0

    @property
    def current_assignment_id(self) -> "UUID | None":
        return self.stage_assignments.get(self.current_stage_index)


class RotationPlanNotFound(Exception):
    pass


class EnrollmentNotFound(Exception):
    pass


class AlreadyEnrolled(Exception):
    pass


class NoNextStage(Exception):
    pass


class StageIndexOutOfRange(Exception):
    pass


class ConcurrentModification(Exception):
    pass
