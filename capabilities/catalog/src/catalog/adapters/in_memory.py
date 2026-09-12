from __future__ import annotations

from dataclasses import replace
from typing import Optional
from uuid import UUID

from ..domain import (
    AnnualLeave,
    AssociateProfile,
    AssociateSkill,
    CcaActivity,
    CcaActivityNotFound,
    InterestActivity,
    InterestFlag,
    Skill,
    SkillNotFound,
    Team,
    TeamNotFound,
    UploadAudit,
)


def _copy_profile(p: AssociateProfile) -> AssociateProfile:
    return replace(
        p, experience=list(p.experience), project_highlights=list(p.project_highlights)
    )


class InMemoryCatalogRepo:
    def __init__(self) -> None:
        self._skills: dict[UUID, Skill] = {}
        self._teams: dict[UUID, Team] = {}
        self._cca_activities: dict[UUID, CcaActivity] = {}
        self._associate_skills: dict[UUID, AssociateSkill] = {}
        self._profiles: dict[UUID, AssociateProfile] = {}  # keyed by agent_id
        self._interest_flags: dict[UUID, InterestFlag] = {}
        self._interest_activity: dict[UUID, InterestActivity] = {}  # keyed by agent_id
        self._leave: dict[UUID, AnnualLeave] = {}
        self._upload_audits: dict[UUID, UploadAudit] = {}

    # -- Skills --
    def add_skill(self, skill: Skill) -> None:
        self._skills[skill.id] = replace(skill)

    def get_skill(self, skill_id: UUID) -> Skill:
        try:
            return replace(self._skills[skill_id])
        except KeyError:
            raise SkillNotFound(skill_id) from None

    def list_skills(self) -> list[Skill]:
        return [replace(s) for s in self._skills.values()]

    # -- Teams --
    def add_team(self, team: Team) -> None:
        self._teams[team.id] = replace(team)

    def get_team(self, team_id: UUID) -> Team:
        try:
            return replace(self._teams[team_id])
        except KeyError:
            raise TeamNotFound(team_id) from None

    def list_teams(self) -> list[Team]:
        return [replace(t) for t in self._teams.values()]

    # -- CCA activities --
    def add_cca_activity(self, cca: CcaActivity) -> None:
        self._cca_activities[cca.id] = replace(cca)

    def get_cca_activity(self, cca_id: UUID) -> CcaActivity:
        try:
            return replace(self._cca_activities[cca_id])
        except KeyError:
            raise CcaActivityNotFound(cca_id) from None

    def list_cca_activities(self) -> list[CcaActivity]:
        return [replace(c) for c in self._cca_activities.values()]

    def update_cca_activity(self, cca: CcaActivity) -> None:
        if cca.id not in self._cca_activities:
            raise CcaActivityNotFound(cca.id)
        self._cca_activities[cca.id] = replace(cca)

    # -- Associate-declared skills --
    def add_associate_skill(self, associate_skill: AssociateSkill) -> None:
        self._associate_skills[associate_skill.id] = replace(associate_skill)

    def list_associate_skills(self, agent_id: UUID) -> list[AssociateSkill]:
        return [
            replace(s) for s in self._associate_skills.values() if s.agent_id == agent_id
        ]

    # -- Associate profile --
    def get_profile(self, agent_id: UUID) -> Optional[AssociateProfile]:
        profile = self._profiles.get(agent_id)
        return _copy_profile(profile) if profile else None

    def upsert_profile(self, profile: AssociateProfile) -> None:
        self._profiles[profile.agent_id] = _copy_profile(profile)

    # -- Interest signaling --
    def add_interest_flag(self, flag: InterestFlag) -> None:
        self._interest_flags[flag.id] = replace(flag)

    def update_interest_flag(self, flag: InterestFlag) -> None:
        if flag.id not in self._interest_flags:
            raise ValueError(f"InterestFlag {flag.id} not found")
        self._interest_flags[flag.id] = replace(flag)

    def list_interest_flags(self, agent_id: UUID) -> list[InterestFlag]:
        return [
            replace(f) for f in self._interest_flags.values() if f.agent_id == agent_id
        ]

    def get_interest_activity(self, agent_id: UUID) -> Optional[InterestActivity]:
        activity = self._interest_activity.get(agent_id)
        return replace(activity) if activity else None

    def upsert_interest_activity(self, activity: InterestActivity) -> None:
        self._interest_activity[activity.agent_id] = replace(activity)

    # -- Annual leave --
    def add_leave(self, leave: AnnualLeave) -> None:
        self._leave[leave.id] = replace(leave)

    def list_leave(self, agent_id: UUID) -> list[AnnualLeave]:
        return [replace(l) for l in self._leave.values() if l.agent_id == agent_id]

    # -- Upload audit log --
    def add_upload_audit(self, audit: UploadAudit) -> None:
        self._upload_audits[audit.id] = replace(audit)

    def list_upload_audits(self) -> list[UploadAudit]:
        return sorted(
            (replace(a) for a in self._upload_audits.values()),
            key=lambda a: a.uploaded_at,
            reverse=True,
        )
