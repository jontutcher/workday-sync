"""Tests for workday_sync.parser."""

from datetime import date, datetime
from pathlib import Path

import pytest

from workday_sync.models import AbsenceRequest
from workday_sync.parser import ParseResult, parse_xlsx


class TestParseXlsx:
    def test_returns_parse_result(self, sample_xlsx: Path) -> None:
        result = parse_xlsx(sample_xlsx)
        assert isinstance(result, ParseResult)

    def test_requests_are_absence_requests(self, sample_xlsx: Path) -> None:
        requests, _ = parse_xlsx(sample_xlsx)
        assert isinstance(requests, list)
        assert all(isinstance(r, AbsenceRequest) for r in requests)

    def test_correct_number_of_rows(self, sample_xlsx: Path) -> None:
        requests, _ = parse_xlsx(sample_xlsx)
        assert len(requests) == 6

    def test_user_name_extracted_from_title_row(self, sample_xlsx: Path) -> None:
        requests, _ = parse_xlsx(sample_xlsx)
        assert all(r.user_name == "Alex Sample" for r in requests)

    def test_full_day_entry(self, sample_xlsx: Path) -> None:
        requests, _ = parse_xlsx(sample_xlsx)
        entry = next(r for r in requests if r.date == date(2025, 3, 3))
        assert entry.hours == 8.0
        assert entry.is_full_day is True
        assert entry.comment is None
        assert entry.status == "Approved"
        assert entry.leave_type == "Paid Time Off"

    def test_half_day_with_pm_comment(self, sample_xlsx: Path) -> None:
        requests, _ = parse_xlsx(sample_xlsx)
        entry = next(r for r in requests if r.date == date(2025, 3, 24))
        assert entry.hours == 4.0
        assert entry.is_half_day is True
        assert entry.comment == "PM Leave"

    def test_half_day_with_morning_comment(self, sample_xlsx: Path) -> None:
        requests, _ = parse_xlsx(sample_xlsx)
        entry = next(r for r in requests if r.date == date(2025, 3, 17))
        assert entry.hours == 4.0
        assert entry.comment == "Morning appointment"

    def test_half_day_without_am_pm_indicator(self, sample_xlsx: Path) -> None:
        """Mar 31 is a 4h day whose comment has no AM/PM keyword."""
        requests, _ = parse_xlsx(sample_xlsx)
        entry = next(r for r in requests if r.date == date(2025, 3, 31))
        assert entry.hours == 4.0
        assert entry.comment == "Dentist"

    def test_half_day_without_am_pm_returns_warning(self, sample_xlsx: Path) -> None:
        _, warnings = parse_xlsx(sample_xlsx)
        assert any("2025-03-31" in w for w in warnings)

    def test_no_python_warnings_emitted(self, sample_xlsx: Path) -> None:
        """parse_xlsx must not call warnings.warn — callers receive warnings via ParseResult."""
        import warnings as stdlib_warnings
        with stdlib_warnings.catch_warnings(record=True) as caught:
            stdlib_warnings.simplefilter("always")
            parse_xlsx(sample_xlsx)
        user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
        assert user_warnings == []

    def test_dates_are_date_objects(self, sample_xlsx: Path) -> None:
        requests, _ = parse_xlsx(sample_xlsx)
        assert all(isinstance(r.date, date) for r in requests)

    def test_days_unit_normalised_to_hours(self, sample_xlsx: Path) -> None:
        """A row with Requested=1, Unit=Days should produce hours=8.0."""
        requests, _ = parse_xlsx(sample_xlsx)
        entry = next(r for r in requests if r.date == date(2025, 4, 7))
        assert entry.hours == 8.0
        assert entry.is_full_day is True

    def test_unsupported_unit_raises(self, make_xlsx) -> None:
        bad_xlsx = make_xlsx("Test User", [
            (datetime(2025, 1, 1), "Wed", "Paid Time Off", 1.0, "Fortnights", None, "Approved"),
        ])
        with pytest.raises(ValueError, match="Unsupported unit"):
            parse_xlsx(bad_xlsx)

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_xlsx(Path("nonexistent.xlsx"))
