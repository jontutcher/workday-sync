"""Tests for workday_sync.models."""

from datetime import date

import pytest

from workday_sync.models import AbsenceRequest, HalfDayPeriod


class TestAbsenceRequest:
    def test_full_day_creation(self) -> None:
        req = AbsenceRequest(
            date=date(2026, 8, 28),
            hours=8.0,
            leave_type="Paid Time Off",
            comment=None,
            status="Approved",
            user_name="Jon Tutcher",
        )
        assert req.date == date(2026, 8, 28)
        assert req.hours == 8.0
        assert req.is_full_day is True
        assert req.is_half_day is False

    def test_half_day_creation(self) -> None:
        req = AbsenceRequest(
            date=date(2026, 5, 22),
            hours=4.0,
            leave_type="Paid Time Off",
            comment="PM Leave",
            status="Approved",
            user_name="Jon Tutcher",
        )
        assert req.is_full_day is False
        assert req.is_half_day is True

    def test_event_title_uses_leave_type(self) -> None:
        req = AbsenceRequest(
            date=date(2026, 8, 28),
            hours=8.0,
            leave_type="Paid Time Off",
            comment=None,
            status="Approved",
            user_name="Jon Tutcher",
        )
        assert req.event_title == "Jon Tutcher - Paid Time Off"

    def test_event_title_reflects_sick_leave(self) -> None:
        req = AbsenceRequest(
            date=date(2026, 8, 28),
            hours=8.0,
            leave_type="Sick Time",
            comment=None,
            status="Approved",
            user_name="Jon Tutcher",
        )
        assert req.event_title == "Jon Tutcher - Sick Time"


class TestHalfDayPeriod:
    @pytest.mark.parametrize(
        "comment,expected",
        [
            ("morning leave", HalfDayPeriod.MORNING),
            ("AM leave", HalfDayPeriod.MORNING),
            ("Taking the morning off", HalfDayPeriod.MORNING),
            ("afternoon", HalfDayPeriod.AFTERNOON),
            ("PM Leave", HalfDayPeriod.AFTERNOON),
            ("Afternoon appointment", HalfDayPeriod.AFTERNOON),
            ("Some other comment", HalfDayPeriod.UNKNOWN),
            (None, HalfDayPeriod.UNKNOWN),
            ("", HalfDayPeriod.UNKNOWN),
        ],
    )
    def test_from_comment(self, comment: str | None, expected: HalfDayPeriod) -> None:
        assert HalfDayPeriod.from_comment(comment) == expected
