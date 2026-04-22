"""Tests for workday_sync.parser."""

import warnings
from datetime import date
from pathlib import Path

import pytest

from workday_sync.models import AbsenceRequest
from workday_sync.parser import parse_xlsx


class TestParseXlsx:
    def test_returns_list_of_absence_requests(self, sample_xlsx: Path) -> None:
        requests = parse_xlsx(sample_xlsx)
        assert isinstance(requests, list)
        assert all(isinstance(r, AbsenceRequest) for r in requests)

    def test_correct_number_of_rows(self, sample_xlsx: Path) -> None:
        requests = parse_xlsx(sample_xlsx)
        assert len(requests) == 5

    def test_user_name_extracted_from_title_row(self, sample_xlsx: Path) -> None:
        requests = parse_xlsx(sample_xlsx)
        assert all(r.user_name == "Alex Sample" for r in requests)

    def test_full_day_entry(self, sample_xlsx: Path) -> None:
        requests = parse_xlsx(sample_xlsx)
        entry = next(r for r in requests if r.date == date(2025, 3, 3))
        assert entry.hours == 8.0
        assert entry.is_full_day is True
        assert entry.comment is None
        assert entry.status == "Approved"
        assert entry.leave_type == "Paid Time Off"

    def test_half_day_with_pm_comment(self, sample_xlsx: Path) -> None:
        requests = parse_xlsx(sample_xlsx)
        entry = next(r for r in requests if r.date == date(2025, 3, 24))
        assert entry.hours == 4.0
        assert entry.is_half_day is True
        assert entry.comment == "PM Leave"

    def test_half_day_with_morning_comment(self, sample_xlsx: Path) -> None:
        requests = parse_xlsx(sample_xlsx)
        entry = next(r for r in requests if r.date == date(2025, 3, 17))
        assert entry.hours == 4.0
        assert entry.comment == "Morning appointment"

    def test_half_day_without_am_pm_indicator(self, sample_xlsx: Path) -> None:
        """Mar 31 is a 4h day whose comment has no AM/PM keyword."""
        requests = parse_xlsx(sample_xlsx)
        entry = next(r for r in requests if r.date == date(2025, 3, 31))
        assert entry.hours == 4.0
        assert entry.comment == "Dentist"

    def test_half_day_without_am_pm_emits_warning(self, sample_xlsx: Path) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            parse_xlsx(sample_xlsx)
        msgs = [str(w.message) for w in caught if issubclass(w.category, UserWarning)]
        assert any("2025-03-31" in m for m in msgs)

    def test_dates_are_date_objects(self, sample_xlsx: Path) -> None:
        requests = parse_xlsx(sample_xlsx)
        assert all(isinstance(r.date, date) for r in requests)

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_xlsx(Path("nonexistent.xlsx"))
