"""Application service: the one place screens (Streamlit) call into for
catalog + associate self-service operations — never the repo directly.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from .domain import (
    AnnualLeave,
    AssociateProfile,
    AssociateSkill,
    CcaActivity,
    CcaStatus,
    InterestActivity,
    InterestFlag,
    InterestTargetType,
    Skill,
    SkillSource,
    Team,
    UploadAudit,
    UploadKind,
)
from .ports import CatalogRepo


def _as_utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo on datetime round-trip regardless of the
    column's timezone=True flag (same quirk documented for
    rotation_plan's Enrollment.stage_started_at) — treat a naive value
    read back from storage as UTC rather than let a naive/aware
    comparison raise TypeError."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class CatalogService:
    def __init__(self, repo: CatalogRepo):
        self._repo = repo

    # -- Setup catalogs --

    def add_skill(self, name: str) -> Skill:
        skill = Skill(name=name)
        self._repo.add_skill(skill)
        return skill

    def list_skills(self) -> list[Skill]:
        return self._repo.list_skills()

    def add_team(self, name: str, manager_id: UUID) -> Team:
        team = Team(name=name, manager_id=manager_id)
        self._repo.add_team(team)
        return team

    def list_teams(self) -> list[Team]:
        return self._repo.list_teams()

    def add_cca_activity(self, name: str, organizer_manager_id: UUID) -> CcaActivity:
        cca = CcaActivity(name=name, organizer_manager_id=organizer_manager_id)
        self._repo.add_cca_activity(cca)
        return cca

    def list_cca_activities(self) -> list[CcaActivity]:
        return self._repo.list_cca_activities()

    def set_cca_status(self, cca_id: UUID, status: CcaStatus) -> CcaActivity:
        cca = self._repo.get_cca_activity(cca_id)
        cca.status = status
        self._repo.update_cca_activity(cca)
        return cca

    # -- Associate-declared skills --

    def declare_associate_skill(
        self,
        agent_id: UUID,
        skill_id: UUID,
        source: SkillSource,
        source_detail: str = "",
    ) -> AssociateSkill:
        self._repo.get_skill(skill_id)  # raises SkillNotFound if missing
        associate_skill = AssociateSkill(
            agent_id=agent_id, skill_id=skill_id, source=source, source_detail=source_detail
        )
        self._repo.add_associate_skill(associate_skill)
        return associate_skill

    def list_associate_skills(self, agent_id: UUID) -> list[AssociateSkill]:
        return self._repo.list_associate_skills(agent_id)

    # -- Associate profile --

    def get_profile(self, agent_id: UUID) -> AssociateProfile | None:
        return self._repo.get_profile(agent_id)

    def update_profile(self, profile: AssociateProfile) -> AssociateProfile:
        """Always self-editable, never frozen (per spec) — this is a
        plain upsert, no freeze/version gate like GoalSetting/scores."""
        profile.updated_at = datetime.now(timezone.utc)
        self._repo.upsert_profile(profile)
        return profile

    # -- Interest signaling --

    def flag_interest(
        self, agent_id: UUID, target_type: InterestTargetType, target_id: UUID
    ) -> InterestFlag:
        flag = InterestFlag(agent_id=agent_id, target_type=target_type, target_id=target_id)
        self._repo.add_interest_flag(flag)
        self._touch_raised(agent_id)
        return flag

    def unflag_interest(self, agent_id: UUID, flag_id: UUID) -> None:
        for flag in self._repo.list_interest_flags(agent_id):
            if flag.id == flag_id:
                flag.active = False
                self._repo.update_interest_flag(flag)
                self._touch_raised(agent_id)
                return
        raise ValueError(f"InterestFlag {flag_id} not found for agent {agent_id}")

    def list_interests(self, agent_id: UUID, active_only: bool = True) -> list[InterestFlag]:
        flags = self._repo.list_interest_flags(agent_id)
        return [f for f in flags if f.active] if active_only else flags

    def _touch_raised(self, agent_id: UUID) -> None:
        activity = self._repo.get_interest_activity(agent_id) or InterestActivity(
            agent_id=agent_id
        )
        activity.raised_at = datetime.now(timezone.utc)
        self._repo.upsert_interest_activity(activity)

    def mark_interest_seen(self, agent_id: UUID) -> None:
        """Called when the admin opens this Agent's profile — clears the
        highlight badge (per spec: "opening the profile is what clears
        it")."""
        activity = self._repo.get_interest_activity(agent_id) or InterestActivity(
            agent_id=agent_id
        )
        activity.seen_at = datetime.now(timezone.utc)
        self._repo.upsert_interest_activity(activity)

    def has_unseen_interest_change(self, agent_id: UUID) -> bool:
        activity = self._repo.get_interest_activity(agent_id)
        if activity is None or activity.raised_at is None:
            return False
        if activity.seen_at is None:
            return True
        return _as_utc(activity.raised_at) > _as_utc(activity.seen_at)

    # -- Annual leave --

    def declare_leave(
        self, agent_id: UUID, start_date: date, end_date: date, note: str = ""
    ) -> AnnualLeave:
        leave = AnnualLeave(
            agent_id=agent_id, start_date=start_date, end_date=end_date, note=note
        )
        self._repo.add_leave(leave)
        return leave

    def list_leave(self, agent_id: UUID) -> list[AnnualLeave]:
        return self._repo.list_leave(agent_id)

    # -- Upload audit log (Phase 5) --

    def log_upload(
        self,
        uploaded_by_name: str,
        kind: UploadKind,
        filename: str,
        raw_file: bytes,
        summary: dict | None = None,
        errors: list | None = None,
        uploaded_by: UUID | None = None,
    ) -> UploadAudit:
        audit = UploadAudit(
            uploaded_by_name=uploaded_by_name,
            uploaded_by=uploaded_by,
            kind=kind,
            filename=filename,
            raw_file=raw_file,
            summary=summary or {},
            errors=errors or [],
        )
        self._repo.add_upload_audit(audit)
        return audit

    def list_uploads(self) -> list[UploadAudit]:
        return self._repo.list_upload_audits()
