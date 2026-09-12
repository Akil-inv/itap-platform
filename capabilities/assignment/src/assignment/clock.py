"""Single source of truth for "today" across the package. Standardizes on
UTC rather than server-local time — for a geographically distributed
program, server-local `date.today()` makes elapsed-day boundaries depend
on which timezone the host happens to be in. UTC doesn't solve per-user
local time, but it removes that host-dependent ambiguity and gives one
documented, consistent clock.
"""
from __future__ import annotations

from datetime import date, datetime, timezone


def today() -> date:
    return datetime.now(timezone.utc).date()
