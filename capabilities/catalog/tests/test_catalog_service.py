from datetime import date
from uuid import uuid4

import pytest

from catalog.domain import CcaStatus, InterestTargetType, SkillSource, UploadKind
from catalog.service import CatalogService


@pytest.fixture
def service(catalog_repo):
    """Parametrized over both adapters (mirrors rotation_plan's service
    tests, per docs/architecture.md's note that a service's own tests
    should run against both adapters, not just InMemory)."""
    return CatalogService(catalog_repo)


def test_add_skill_then_list(service):
    service.add_skill("Python")
    service.add_skill("SQL")

    assert {s.name for s in service.list_skills()} == {"Python", "SQL"}


def test_add_team_then_list(service):
    manager_id = uuid4()
    service.add_team("Platform Team", manager_id)

    teams = service.list_teams()
    assert len(teams) == 1
    assert teams[0].manager_id == manager_id


def test_cca_activity_open_by_default_then_closeable(service):
    cca = service.add_cca_activity("Hackathon", uuid4())
    assert cca.status == CcaStatus.OPEN

    closed = service.set_cca_status(cca.id, CcaStatus.CLOSED)
    assert closed.status == CcaStatus.CLOSED
    assert service.list_cca_activities()[0].status == CcaStatus.CLOSED


def test_declare_associate_skill_self_and_engagement(service):
    agent_id = uuid4()
    skill = service.add_skill("Public Speaking")

    service.declare_associate_skill(agent_id, skill.id, SkillSource.SELF)
    service.declare_associate_skill(
        agent_id, skill.id, SkillSource.ENGAGEMENT, source_detail="Data Team, Mar 2026"
    )

    entries = service.list_associate_skills(agent_id)
    assert {e.source for e in entries} == {SkillSource.SELF, SkillSource.ENGAGEMENT}


def test_profile_starts_absent_then_updatable(service):
    agent_id = uuid4()
    assert service.get_profile(agent_id) is None

    from catalog.domain import AssociateProfile

    service.update_profile(AssociateProfile(agent_id=agent_id, bio="First draft"))
    assert service.get_profile(agent_id).bio == "First draft"

    service.update_profile(AssociateProfile(agent_id=agent_id, bio="Revised anytime"))
    assert service.get_profile(agent_id).bio == "Revised anytime"


def test_flagging_interest_raises_the_highlight(service):
    agent_id = uuid4()
    assert service.has_unseen_interest_change(agent_id) is False

    service.flag_interest(agent_id, InterestTargetType.TEAM, uuid4())

    assert service.has_unseen_interest_change(agent_id) is True


def test_opening_the_profile_clears_the_highlight(service):
    agent_id = uuid4()
    service.flag_interest(agent_id, InterestTargetType.CCA, uuid4())
    assert service.has_unseen_interest_change(agent_id) is True

    service.mark_interest_seen(agent_id)

    assert service.has_unseen_interest_change(agent_id) is False


def test_a_later_flag_change_raises_the_highlight_again(service):
    agent_id = uuid4()
    flag = service.flag_interest(agent_id, InterestTargetType.TEAM, uuid4())
    service.mark_interest_seen(agent_id)
    assert service.has_unseen_interest_change(agent_id) is False

    service.unflag_interest(agent_id, flag.id)

    assert service.has_unseen_interest_change(agent_id) is True


def test_unflagging_unknown_flag_raises(service):
    with pytest.raises(ValueError):
        service.unflag_interest(uuid4(), uuid4())


def test_list_interests_defaults_to_active_only(service):
    agent_id = uuid4()
    keep = service.flag_interest(agent_id, InterestTargetType.TEAM, uuid4())
    drop = service.flag_interest(agent_id, InterestTargetType.CCA, uuid4())
    service.unflag_interest(agent_id, drop.id)

    active = service.list_interests(agent_id)
    everything = service.list_interests(agent_id, active_only=False)

    assert [f.id for f in active] == [keep.id]
    assert len(everything) == 2


def test_declare_leave_is_informational_only(service):
    agent_id = uuid4()

    service.declare_leave(agent_id, date(2026, 7, 1), date(2026, 7, 10), note="Family trip")

    leave = service.list_leave(agent_id)
    assert len(leave) == 1
    assert leave[0].note == "Family trip"


def test_log_upload_then_list_uploads(service):
    service.log_upload(
        "Priya", UploadKind.WORKBOOK, "setup.xlsx", b"data",
        summary={"created": 2}, errors=[],
    )

    uploads = service.list_uploads()
    assert len(uploads) == 1
    assert uploads[0].filename == "setup.xlsx"
    assert uploads[0].summary == {"created": 2}
