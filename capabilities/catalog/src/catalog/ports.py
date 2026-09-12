"""Port for the catalog capability. Kept as one Protocol across several
entity kinds (Skill/Team/CcaActivity catalogs, AssociateSkill,
AssociateProfile, InterestFlag/InterestActivity, AnnualLeave) — same
reasoning as `assignment.AssignmentRepo`: these are small, low-churn
records with no independent lifecycle of their own worth a separate port
each, and splitting them would add indirection without a present need.
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Protocol
from uuid import UUID

from .domain import (
    AnnualLeave,
    AssociateProfile,
    AssociateSkill,
    CcaActivity,
    InterestActivity,
    InterestFlag,
    Skill,
    Team,
    UploadAudit,
)


class CatalogRepo(Protocol):
    # -- Skills catalog --
    def add_skill(self, skill: Skill) -> None: ...

    def get_skill(self, skill_id: UUID) -> Skill: ...

    def list_skills(self) -> list[Skill]: ...

    # -- Teams catalog --
    def add_team(self, team: Team) -> None: ...

    def get_team(self, team_id: UUID) -> Team: ...

    def list_teams(self) -> list[Team]: ...

    # -- CCA catalog --
    def add_cca_activity(self, cca: CcaActivity) -> None: ...

    def get_cca_activity(self, cca_id: UUID) -> CcaActivity: ...

    def list_cca_activities(self) -> list[CcaActivity]: ...

    def update_cca_activity(self, cca: CcaActivity) -> None:
        """Status flip (open/closed) or other field update — no
        concurrency contract needed yet, unlike Assignment/RotationPlan:
        this is single-admin Setup data, not a multi-actor record."""
        ...

    # -- Associate-declared skills --
    def add_associate_skill(self, associate_skill: AssociateSkill) -> None: ...

    def list_associate_skills(self, agent_id: UUID) -> list[AssociateSkill]: ...

    # -- Associate profile (one per agent) --
    def get_profile(self, agent_id: UUID) -> Optional[AssociateProfile]: ...

    def upsert_profile(self, profile: AssociateProfile) -> None: ...

    # -- Interest signaling --
    def add_interest_flag(self, flag: InterestFlag) -> None: ...

    def update_interest_flag(self, flag: InterestFlag) -> None: ...

    def list_interest_flags(self, agent_id: UUID) -> list[InterestFlag]: ...

    def get_interest_activity(self, agent_id: UUID) -> Optional[InterestActivity]: ...

    def upsert_interest_activity(self, activity: InterestActivity) -> None: ...

    # -- Annual leave --
    def add_leave(self, leave: AnnualLeave) -> None: ...

    def list_leave(self, agent_id: UUID) -> list[AnnualLeave]: ...

    # -- Upload audit log (Phase 5) --
    def add_upload_audit(self, audit: UploadAudit) -> None: ...

    def list_upload_audits(self) -> list[UploadAudit]:
        """Newest first — the feed the read-only admin screen lists
        from."""
        ...
