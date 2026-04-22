"""Tests for workday_sync.ics_builder."""

from datetime import date

import pytest
import pytz
from icalendar import Calendar

from workday_sync.ics_builder import build_ics
from workday_sync.models import AbsenceRequest


def make_request(**kwargs) -> AbsenceRequest:
    defaults = dict(
        date=date(2026, 8, 28),
        hours=8.0,
        leave_type="Paid Time Off",
        comment=None,
        status="Approved",
        user_name="Jon Tutcher",
    )
    defaults.update(kwargs)
    return AbsenceRequest(**defaults)


def parse_ics(ics_str: str) -> Calendar:
    return Calendar.from_ical(ics_str)


def get_events(cal: Calendar) -> list:
    return [c for c in cal.walk() if c.name == "VEVENT"]


class TestBuildIcs:
    def test_returns_string(self) -> None:
        result = build_ics([make_request()], timezone="Europe/London")
        assert isinstance(result, str)

    def test_valid_icalendar(self) -> None:
        result = build_ics([make_request()], timezone="Europe/London")
        cal = parse_ics(result)
        assert cal is not None

    def test_one_event_per_request(self) -> None:
        requests = [
            make_request(date=date(2026, 8, 28)),
            make_request(date=date(2026, 8, 27)),
        ]
        cal = parse_ics(build_ics(requests, timezone="Europe/London"))
        assert len(get_events(cal)) == 2

    def test_event_title_uses_leave_type(self) -> None:
        cal = parse_ics(build_ics([make_request()], timezone="Europe/London"))
        event = get_events(cal)[0]
        assert str(event["SUMMARY"]) == "Jon Tutcher - Paid Time Off"

    def test_event_title_reflects_sick_leave(self) -> None:
        cal = parse_ics(build_ics([make_request(leave_type="Sick Time")], timezone="Europe/London"))
        event = get_events(cal)[0]
        assert str(event["SUMMARY"]) == "Jon Tutcher - Sick Time"

    def test_full_day_starts_at_0800(self) -> None:
        cal = parse_ics(build_ics([make_request(hours=8.0)], timezone="Europe/London"))
        event = get_events(cal)[0]
        dt = event["DTSTART"].dt
        assert dt.hour == 8
        assert dt.minute == 0

    def test_full_day_ends_at_1800(self) -> None:
        cal = parse_ics(build_ics([make_request(hours=8.0)], timezone="Europe/London"))
        event = get_events(cal)[0]
        dt = event["DTEND"].dt
        assert dt.hour == 18
        assert dt.minute == 0

    def test_morning_half_day_0800_to_1200(self) -> None:
        req = make_request(hours=4.0, comment="morning leave")
        cal = parse_ics(build_ics([req], timezone="Europe/London"))
        event = get_events(cal)[0]
        assert event["DTSTART"].dt.hour == 8
        assert event["DTEND"].dt.hour == 12

    def test_afternoon_half_day_1300_to_1800(self) -> None:
        req = make_request(hours=4.0, comment="PM Leave")
        cal = parse_ics(build_ics([req], timezone="Europe/London"))
        event = get_events(cal)[0]
        assert event["DTSTART"].dt.hour == 13
        assert event["DTEND"].dt.hour == 18

    def test_unknown_half_day_defaults_to_morning(self) -> None:
        req = make_request(hours=4.0, comment="May or may not be needed")
        cal = parse_ics(build_ics([req], timezone="Europe/London"))
        event = get_events(cal)[0]
        assert event["DTSTART"].dt.hour == 8
        assert event["DTEND"].dt.hour == 12

    def test_timezone_applied_to_events(self) -> None:
        cal = parse_ics(build_ics([make_request()], timezone="America/New_York"))
        event = get_events(cal)[0]
        dt = event["DTSTART"].dt
        assert dt.tzinfo is not None
        tz_name = dt.tzname()
        assert tz_name in ("EST", "EDT")

    def test_events_marked_opaque(self) -> None:
        cal = parse_ics(build_ics([make_request()], timezone="Europe/London"))
        event = get_events(cal)[0]
        assert str(event.get("TRANSP", "")) == "OPAQUE"

    def test_empty_list_produces_valid_calendar(self) -> None:
        result = build_ics([], timezone="Europe/London")
        cal = parse_ics(result)
        assert len(get_events(cal)) == 0


class TestBuildIcsOutOfOffice:
    def test_no_oof_extension_by_default(self) -> None:
        cal = parse_ics(build_ics([make_request()], timezone="Europe/London"))
        event = get_events(cal)[0]
        assert event.get("X-MICROSOFT-CDO-BUSYSTATUS") is None

    def test_oof_extension_when_flag_set(self) -> None:
        cal = parse_ics(
            build_ics([make_request()], timezone="Europe/London", out_of_office=True)
        )
        event = get_events(cal)[0]
        assert str(event["X-MICROSOFT-CDO-BUSYSTATUS"]) == "OOF"
