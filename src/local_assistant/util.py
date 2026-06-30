"""Small shared helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil import parser as dateparser

from .config import settings


def tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def now() -> datetime:
    return datetime.now(tz())


def parse_when(value: str) -> datetime:
    """Parse an ISO8601 or loosely-formatted datetime into a tz-aware datetime.

    The model is asked to emit ISO8601 (it gets the current time in the system
    prompt); this is a tolerant fallback for relative-ish strings.
    """
    value = value.strip()
    lowered = value.lower()
    base = now()
    if lowered in ("tomorrow", "завтра"):
        return base.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if lowered in ("today", "сегодня"):
        return base.replace(hour=9, minute=0, second=0, microsecond=0)
    dt = dateparser.parse(value)
    if dt is None:
        raise ValueError(f"cannot parse datetime: {value!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz())
    return dt


def in_quiet_hours(at: datetime | None = None) -> bool:
    at = at or now()
    try:
        start_s, end_s = settings.quiet_hours.split("-")
        sh, sm = (int(x) for x in start_s.split(":"))
        eh, em = (int(x) for x in end_s.split(":"))
    except Exception:
        return False
    start = at.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end = at.replace(hour=eh, minute=em, second=0, microsecond=0)
    if start <= end:
        return start <= at <= end
    return at >= start or at <= end  # window wraps midnight
