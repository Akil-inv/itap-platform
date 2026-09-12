from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from catalog.domain import (
    AnnualLeave,
    AssociateProfile,
    AssociateSkill,
    CcaActivity,
    CcaActivityNotFound,
    CcaStatus,
    ExperienceEntry,
    InterestActivity,
    InterestFlag,
    InterestTargetType,
    ProjectHighlight,
    Skill,
    SkillNotFound,
    SkillSource,
    Team,
    TeamNotFound,
    UploadAudit,
    UploadKind,
)


# -- Skills --


def test_add_and_get_skill_round_trips(catalog_repo):
    skill = Skill(name="Python")
    catalog_repo.add_skill(skill)

    fetched = catalog_repo.get_skill(skill.id)

    assert fetched.id == skill.id
    assert fetched.name == "Python"


def test_get_missing_skill_raises(catalog_repo):
    with pytest.raises(SkillNotFound):
        catalog_repo.get_skill(uuid4())


def test_list_skills_returns_every_skill(catalog_repo):
    catalog_repo.add_skill(Skill(name="Python"))
    catalog_repo.add_skill(Skill(name="SQL"))

    assert {s.name for s in catalog_repo.list_skills()} == {"Python", "SQL"}


# -- Teams --


def test_add_and_get_team_round_trips(catalog_repo):
    manager_id = uuid4()
    team = Team(name="Platform Team", manager_id=manager_id)
    catalog_repo.add_team(team)

    fetched = catalog_repo.get_team(team.id)

    assert fetched.name == "Platform Team"
    assert fetched.manager_id == manager_id


def test_get_missing_team_raises(catalog_repo):
    with pytest.raises(TeamNotFound):
        catalog_repo.get_team(uuid4())


def test_two_teams_can_share_the_same_manager(catalog_repo):
    """MVP is one-team-one-manager, but the schema must not block a
    manager overseeing more than one Team later — see domain.py's Team
    docstring."""
    manager_id = uuid4()
    catalog_repo.add_team(Team(name="Platform Team", manager_id=manager_id))
    catalog_repo.add_team(Team(name="Data Team", manager_id=manager_id))

    teams = catalog_repo.list_teams()
    assert {t.manager_id for t in teams} == {manager_id}
    assert len(teams) == 2


# -- CCA activities --


def test_add_and_get_cca_activity_defaults_open(catalog_repo):
    organizer = uuid4()
    cca = CcaActivity(name="Hackathon", organizer_manager_id=organizer)
    catalog_repo.add_cca_activity(cca)

    fetched = catalog_repo.get_cca_activity(cca.id)

    assert fetched.status == CcaStatus.OPEN
    assert fetched.organizer_manager_id == organizer


def test_get_missing_cca_activity_raises(catalog_repo):
    with pytest.raises(CcaActivityNotFound):
        catalog_repo.get_cca_activity(uuid4())


def test_update_cca_activity_status(catalog_repo):
    cca = CcaActivity(name="Brownbag", organizer_manager_id=uuid4())
    catalog_repo.add_cca_activity(cca)

    cca.status = CcaStatus.CLOSED
    catalog_repo.update_cca_activity(cca)

    assert catalog_repo.get_cca_activity(cca.id).status == CcaStatus.CLOSED


def test_update_missing_cca_activity_raises(catalog_repo):
    cca = CcaActivity(name="Ghost", organizer_manager_id=uuid4())
    with pytest.raises(CcaActivityNotFound):
        catalog_repo.update_cca_activity(cca)


# -- Associate-declared skills --


def test_associate_skill_round_trips_with_source(catalog_repo):
    agent_id = uuid4()
    skill = Skill(name="Public Speaking")
    catalog_repo.add_skill(skill)

    catalog_repo.add_associate_skill(
        AssociateSkill(
            agent_id=agent_id,
            skill_id=skill.id,
            source=SkillSource.ENGAGEMENT,
            source_detail="Data Team engagement, Mar 2026",
        )
    )
    catalog_repo.add_associate_skill(
        AssociateSkill(agent_id=agent_id, skill_id=skill.id, source=SkillSource.SELF)
    )

    entries = catalog_repo.list_associate_skills(agent_id)
    assert {e.source for e in entries} == {SkillSource.ENGAGEMENT, SkillSource.SELF}
    engagement_entry = next(e for e in entries if e.source == SkillSource.ENGAGEMENT)
    assert engagement_entry.source_detail == "Data Team engagement, Mar 2026"


def test_list_associate_skills_scoped_to_agent(catalog_repo):
    skill = Skill(name="SQL")
    catalog_repo.add_skill(skill)
    mine, other = uuid4(), uuid4()
    catalog_repo.add_associate_skill(
        AssociateSkill(agent_id=mine, skill_id=skill.id, source=SkillSource.SELF)
    )
    catalog_repo.add_associate_skill(
        AssociateSkill(agent_id=other, skill_id=skill.id, source=SkillSource.SELF)
    )

    assert len(catalog_repo.list_associate_skills(mine)) == 1


# -- Associate profile --


def test_profile_missing_returns_none(catalog_repo):
    assert catalog_repo.get_profile(uuid4()) is None


def test_profile_round_trips_structured_fields(catalog_repo):
    agent_id = uuid4()
    profile = AssociateProfile(
        agent_id=agent_id,
        bio="Loves data pipelines.",
        photo_url="https://example.com/photo.jpg",
        experience=[
            ExperienceEntry(
                title="Data Team Intern",
                description="Built dashboards",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 12, 1),
            )
        ],
        project_highlights=[ProjectHighlight(title="Onboarding bot", description="Saved 10h/wk")],
    )

    catalog_repo.upsert_profile(profile)
    fetched = catalog_repo.get_profile(agent_id)

    assert fetched.bio == "Loves data pipelines."
    assert fetched.photo_url == "https://example.com/photo.jpg"
    assert fetched.experience == [
        ExperienceEntry(
            title="Data Team Intern",
            description="Built dashboards",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 12, 1),
        )
    ]
    assert fetched.project_highlights == [
        ProjectHighlight(title="Onboarding bot", description="Saved 10h/wk")
    ]


def test_upsert_profile_overwrites_existing(catalog_repo):
    agent_id = uuid4()
    catalog_repo.upsert_profile(AssociateProfile(agent_id=agent_id, bio="First draft"))
    catalog_repo.upsert_profile(AssociateProfile(agent_id=agent_id, bio="Updated"))

    assert catalog_repo.get_profile(agent_id).bio == "Updated"


# -- Interest signaling --


def test_interest_flag_round_trips(catalog_repo):
    agent_id, team_id = uuid4(), uuid4()
    catalog_repo.add_interest_flag(
        InterestFlag(agent_id=agent_id, target_type=InterestTargetType.TEAM, target_id=team_id)
    )

    flags = catalog_repo.list_interest_flags(agent_id)
    assert len(flags) == 1
    assert flags[0].active is True
    assert flags[0].target_id == team_id


def test_update_interest_flag_can_deactivate(catalog_repo):
    agent_id, cca_id = uuid4(), uuid4()
    flag = InterestFlag(agent_id=agent_id, target_type=InterestTargetType.CCA, target_id=cca_id)
    catalog_repo.add_interest_flag(flag)

    flag.active = False
    catalog_repo.update_interest_flag(flag)

    assert catalog_repo.list_interest_flags(agent_id)[0].active is False


def test_interest_activity_missing_returns_none(catalog_repo):
    assert catalog_repo.get_interest_activity(uuid4()) is None


def test_interest_activity_round_trips_and_upserts(catalog_repo):
    # SQLite drops tzinfo on datetime round-trip regardless of the
    # column's timezone=True flag (same known quirk documented for
    # rotation_plan's Enrollment.stage_started_at in docs/architecture.md)
    # — compare naively rather than assuming tz-awareness survives.
    agent_id = uuid4()
    raised = datetime(2026, 3, 1, tzinfo=timezone.utc)
    catalog_repo.upsert_interest_activity(InterestActivity(agent_id=agent_id, raised_at=raised))

    fetched = catalog_repo.get_interest_activity(agent_id)
    assert fetched.raised_at.replace(tzinfo=None) == raised.replace(tzinfo=None)
    assert fetched.seen_at is None

    seen = datetime(2026, 3, 2, tzinfo=timezone.utc)
    catalog_repo.upsert_interest_activity(
        InterestActivity(agent_id=agent_id, raised_at=raised, seen_at=seen)
    )

    fetched_seen = catalog_repo.get_interest_activity(agent_id).seen_at
    assert fetched_seen.replace(tzinfo=None) == seen.replace(tzinfo=None)


# -- Annual leave --


def test_leave_round_trips(catalog_repo):
    agent_id = uuid4()
    catalog_repo.add_leave(
        AnnualLeave(
            agent_id=agent_id,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 10),
            note="Family trip",
        )
    )

    leave = catalog_repo.list_leave(agent_id)
    assert len(leave) == 1
    assert leave[0].start_date == date(2026, 7, 1)
    assert leave[0].end_date == date(2026, 7, 10)
    assert leave[0].note == "Family trip"


def test_list_leave_scoped_to_agent(catalog_repo):
    mine, other = uuid4(), uuid4()
    catalog_repo.add_leave(
        AnnualLeave(agent_id=mine, start_date=date(2026, 1, 1), end_date=date(2026, 1, 5))
    )
    catalog_repo.add_leave(
        AnnualLeave(agent_id=other, start_date=date(2026, 2, 1), end_date=date(2026, 2, 5))
    )

    assert len(catalog_repo.list_leave(mine)) == 1


# -- Upload audit log --


def test_upload_audit_round_trips(catalog_repo):
    audit = UploadAudit(
        uploaded_by_name="Priya",
        uploaded_by=uuid4(),
        kind=UploadKind.WORKBOOK,
        filename="setup.xlsx",
        summary={"created": 3, "updated": 1, "skipped": 0, "error": 0},
        errors=["row 4: bad date"],
        raw_file=b"fake-bytes",
    )
    catalog_repo.add_upload_audit(audit)

    fetched = catalog_repo.list_upload_audits()
    assert len(fetched) == 1
    got = fetched[0]
    assert got.uploaded_by_name == "Priya"
    assert got.kind == UploadKind.WORKBOOK
    assert got.filename == "setup.xlsx"
    assert got.summary == {"created": 3, "updated": 1, "skipped": 0, "error": 0}
    assert got.errors == ["row 4: bad date"]
    assert got.raw_file == b"fake-bytes"


def test_upload_audits_listed_newest_first(catalog_repo):
    first = UploadAudit(uploaded_by_name="Priya", kind=UploadKind.WORKBOOK, filename="a.xlsx")
    catalog_repo.add_upload_audit(first)
    second = UploadAudit(uploaded_by_name="Priya", kind=UploadKind.PHOTOS, filename="photos.zip")
    catalog_repo.add_upload_audit(second)

    fetched = catalog_repo.list_upload_audits()
    assert [a.filename for a in fetched] == ["photos.zip", "a.xlsx"]
