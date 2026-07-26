from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True, slots=True)
class WeeklyCalendarWindow:
    iso_week: str
    start: datetime
    end: datetime


def previous_complete_week(
    now: datetime,
    timezone_name: str = "Asia/Shanghai",
) -> WeeklyCalendarWindow:
    """Return the previous Monday-Sunday calendar week in UTC."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    try:
        local_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name != "Asia/Shanghai":
            raise
        # Windows Python installations do not always ship the IANA tzdata
        # package. China Standard Time is UTC+08:00 without daylight saving.
        local_timezone = timezone(timedelta(hours=8), "Asia/Shanghai")
    local_now = now.astimezone(local_timezone)
    current_monday = (
        local_now - timedelta(days=local_now.weekday())
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    start_local = current_monday - timedelta(days=7)
    end_local = current_monday - timedelta(microseconds=1)
    iso_year, iso_number, _ = start_local.isocalendar()
    return WeeklyCalendarWindow(
        iso_week=f"{iso_year}-W{iso_number:02d}",
        start=start_local.astimezone(timezone.utc),
        end=end_local.astimezone(timezone.utc),
    )
