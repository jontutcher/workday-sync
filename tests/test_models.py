"""Tests for workday_sync.models."""

import hashlib
from datetime import date, time

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


class TestTimeWindow:
    def test_full_day_is_0800_to_1800(self) -> None:
        req = AbsenceRequest(date=date(2026, 8, 28), hours=8.0, leave_type="PTO",
                             comment=None, status="Approved", user_name="J")
        assert req.time_window() == (time(8, 0), time(18, 0))

    def test_morning_half_day_is_0800_to_1200(self) -> None:
        req = AbsenceRequest(date=date(2026, 8, 28), hours=4.0, leave_type="PTO",
                             comment="Morning appointment", status="Approved", user_name="J")
        assert req.time_window() == (time(8, 0), time(12, 0))

    def test_afternoon_half_day_is_1300_to_1800(self) -> None:
        req = AbsenceRequest(date=date(2026, 8, 28), hours=4.0, leave_type="PTO",
                             comment="PM Leave", status="Approved", user_name="J")
        assert req.time_window() == (time(13, 0), time(18, 0))

    def test_unknown_half_day_defaults_to_morning(self) -> None:
        req = AbsenceRequest(date=date(2026, 8, 28), hours=4.0, leave_type="PTO",
                             comment="Dentist", status="Approved", user_name="J")
        assert req.time_window() == (time(8, 0), time(12, 0))

    def test_none_comment_defaults_to_morning(self) -> None:
        req = AbsenceRequest(date=date(2026, 8, 28), hours=4.0, leave_type="PTO",
                             comment=None, status="Approved", user_name="J")
        assert req.time_window() == (time(8, 0), time(12, 0))


class TestUniqueKey:
    def _make_key(self, date_str: str, leave_type: str, start: str, end: str, status: str) -> str:
        key_str = "|".join([date_str, leave_type, start, end, status])
        return "absn" + hashlib.sha256(key_str.encode()).hexdigest()

    def test_full_day_key_is_sha256_of_fields(self) -> None:
        req = AbsenceRequest(
            date=date(2026, 8, 28), hours=8.0, leave_type="Paid Time Off",
            comment=None, status="Approved", user_name="Jon Tutcher",
        )
        expected = self._make_key("2026-08-28", "Paid Time Off", "08:00:00", "18:00:00", "Approved")
        assert req.unique_key == expected

    def test_afternoon_half_day_key(self) -> None:
        req = AbsenceRequest(
            date=date(2026, 5, 22), hours=4.0, leave_type="Paid Time Off",
            comment="PM Leave", status="Approved", user_name="Jon Tutcher",
        )
        expected = self._make_key("2026-05-22", "Paid Time Off", "13:00:00", "18:00:00", "Approved")
        assert req.unique_key == expected

    def test_morning_half_day_key(self) -> None:
        req = AbsenceRequest(
            date=date(2026, 5, 22), hours=4.0, leave_type="Paid Time Off",
            comment="morning", status="Approved", user_name="Jon Tutcher",
        )
        expected = self._make_key("2026-05-22", "Paid Time Off", "08:00:00", "12:00:00", "Approved")
        assert req.unique_key == expected

    def test_different_dates_produce_different_keys(self) -> None:
        req1 = AbsenceRequest(
            date=date(2026, 8, 28), hours=8.0, leave_type="PTO",
            comment=None, status="Approved", user_name="J",
        )
        req2 = AbsenceRequest(
            date=date(2026, 8, 29), hours=8.0, leave_type="PTO",
            comment=None, status="Approved", user_name="J",
        )
        assert req1.unique_key != req2.unique_key

    def test_different_statuses_produce_different_keys(self) -> None:
        req1 = AbsenceRequest(
            date=date(2026, 8, 28), hours=8.0, leave_type="PTO",
            comment=None, status="Approved", user_name="J",
        )
        req2 = AbsenceRequest(
            date=date(2026, 8, 28), hours=8.0, leave_type="PTO",
            comment=None, status="Pending", user_name="J",
        )
        assert req1.unique_key != req2.unique_key

    def test_same_fields_produce_same_key(self) -> None:
        req1 = AbsenceRequest(
            date=date(2026, 8, 28), hours=8.0, leave_type="PTO",
            comment=None, status="Approved", user_name="Jon",
        )
        req2 = AbsenceRequest(
            date=date(2026, 8, 28), hours=8.0, leave_type="PTO",
            comment="some comment", status="Approved", user_name="Alice",
        )
        # Same date/type/times/status → same key even with different comment/user_name
        assert req1.unique_key == req2.unique_key

    def test_key_has_wdsync_prefix_and_64_char_hex(self) -> None:
        req = AbsenceRequest(
            date=date(2026, 8, 28), hours=8.0, leave_type="PTO",
            comment=None, status="Approved", user_name="J",
        )
        assert req.unique_key.startswith("absn")
        hex_part = req.unique_key[len("absn"):]
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)


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
