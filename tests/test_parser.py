"""Tests for workday_sync.parser."""

from datetime import date
from pathlib import Path

import pytest

from workday_sync.models import AbsenceRequest
from workday_sync.parser import parse_xlsx

FIXTURE = Path(__file__).parent / "fixtures" / "test_pto.xlsx"


class TestParseXlsx:
    def test_returns_list_of_absence_requests(self) -> None:
        requests = parse_xlsx(FIXTURE)
        assert isinstance(requests, list)
        assert all(isinstance(r, AbsenceRequest) for r in requests)

    def test_correct_number_of_rows(self) -> None:
        requests = parse_xlsx(FIXTURE)
        assert len(requests) == 13

    def test_user_name_extracted_from_title_row(self) -> None:
        requests = parse_xlsx(FIXTURE)
        assert all(r.user_name == "Jon Tutcher" for r in requests)

    def test_full_day_entry(self) -> None:
        requests = parse_xlsx(FIXTURE)
        aug28 = next(r for r in requests if r.date == date(2026, 8, 28))
        assert aug28.hours == 8.0
        assert aug28.is_full_day is True
        assert aug28.comment is None
        assert aug28.status == "Approved"
        assert aug28.leave_type == "Paid Time Off"

    def test_half_day_with_pm_comment(self) -> None:
        requests = parse_xlsx(FIXTURE)
        may22 = next(r for r in requests if r.date == date(2026, 5, 22))
        assert may22.hours == 4.0
        assert may22.is_half_day is True
        assert may22.comment == "PM Leave"

    def test_half_day_without_am_pm_indicator(self) -> None:
        """Jul 31 is a 4h day whose comment has no AM/PM keyword."""
        requests = parse_xlsx(FIXTURE)
        jul31 = next(r for r in requests if r.date == date(2026, 7, 31))
        assert jul31.hours == 4.0
        assert jul31.comment == "May or may not be needed - will confirm closer to the time"

    def test_half_day_without_am_pm_emits_warning(self) -> None:
        import warnings
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            parse_xlsx(FIXTURE)
        msgs = [str(w.message) for w in caught if issubclass(w.category, UserWarning)]
        assert any("2026-07-31" in m for m in msgs)

    def test_dates_are_date_objects(self) -> None:
        requests = parse_xlsx(FIXTURE)
        assert all(isinstance(r.date, date) for r in requests)

    def test_file_not_found_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_xlsx(Path("nonexistent.xlsx"))
