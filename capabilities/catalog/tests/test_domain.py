from datetime import date
from uuid import uuid4

import pytest

from catalog.domain import AnnualLeave, CcaActivity, Skill, Team


def test_skill_rejects_blank_name():
    with pytest.raises(ValueError):
        Skill(name="   ")


def test_team_rejects_blank_name():
    with pytest.raises(ValueError):
        Team(name="", manager_id=uuid4())


def test_cca_activity_rejects_blank_name():
    with pytest.raises(ValueError):
        CcaActivity(name="", organizer_manager_id=uuid4())


def test_annual_leave_rejects_end_before_start():
    with pytest.raises(ValueError):
        AnnualLeave(agent_id=uuid4(), start_date=date(2026, 6, 10), end_date=date(2026, 6, 1))


def test_annual_leave_allows_single_day():
    AnnualLeave(agent_id=uuid4(), start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))
