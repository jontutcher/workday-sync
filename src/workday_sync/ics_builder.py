"""Build a Google Calendar-compatible ICS file from AbsenceRequest objects."""

from __future__ import annotations

import uuid
from datetime import datetime, time

import pytz
from icalendar import Calendar, Event, vText

from workday_sync.models import AbsenceRequest, HalfDayPeriod

# Event time windows (local time)
_FULL_DAY_START = time(8, 0)
_FULL_DAY_END = time(18, 0)
_MORNING_START = time(8, 0)
_MORNING_END = time(12, 0)
_AFTERNOON_START = time(13, 0)
_AFTERNOON_END = time(18, 0)


def build_ics(
    requests: list[AbsenceRequest],
    timezone: str = "Europe/London",
    out_of_office: bool = False,
) -> str:
    """Convert a list of AbsenceRequest objects into an ICS string.

    Args:
        requests: Parsed absence records.
        timezone: IANA timezone name for event datetimes.
        out_of_office: If True, add Out of Office vendor extensions to each event.

    Returns:
        A string containing a valid iCalendar document.
    """
    tz = pytz.timezone(timezone)

    cal = Calendar()
    cal.add("PRODID", "-//workday-sync//workday-sync//EN")
    cal.add("VERSION", "2.0")
    cal.add("CALSCALE", "GREGORIAN")
    cal.add("METHOD", "PUBLISH")

    for req in requests:
        event = _build_event(req, tz, out_of_office)
        cal.add_component(event)

    return cal.to_ical().decode("utf-8")


def _build_event(req: AbsenceRequest, tz: pytz.BaseTzInfo, out_of_office: bool) -> Event:
    """Build a single VEVENT component from an AbsenceRequest."""
    start_time, end_time = _resolve_times(req)

    dtstart = tz.localize(datetime.combine(req.date, start_time))
    dtend = tz.localize(datetime.combine(req.date, end_time))

    event = Event()
    event.add("SUMMARY", req.event_title)
    event.add("DTSTART", dtstart)
    event.add("DTEND", dtend)
    event.add("TRANSP", "OPAQUE")
    event.add("STATUS", "CONFIRMED")
    event.add("UID", str(uuid.uuid4()))

    if out_of_office:
        event.add("X-MICROSOFT-CDO-BUSYSTATUS", vText("OOF"))

    return event


def _resolve_times(req: AbsenceRequest) -> tuple[time, time]:
    """Return (start_time, end_time) for the event based on hours and comment."""
    if req.is_full_day:
        return _FULL_DAY_START, _FULL_DAY_END

    period = HalfDayPeriod.from_comment(req.comment)
    if period is HalfDayPeriod.AFTERNOON:
        return _AFTERNOON_START, _AFTERNOON_END

    # MORNING or UNKNOWN — default to morning
    return _MORNING_START, _MORNING_END
