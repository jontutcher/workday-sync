"""Shared pytest fixtures for workday-sync tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import openpyxl
import pytest


def write_absence_xlsx(path: Path, user_name: str, rows: list[tuple]) -> None:
    """Write a Workday-style absence XLSX to *path* using *rows* as data.

    rows is a list of (date, day_of_week, leave_type, hours, unit, comment, status) tuples.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Absence Requests"

    # Header block matching the real Workday export layout
    ws.append([f"My Absence: {user_name}"])
    ws.append(["Organization", "Acme Corp"])
    ws.append(["Manager(s)", "Jane Manager"])
    ws.append(["Absence Requests"])
    ws.append(["Date", "Day of the Week", "Type", "Requested", "Unit of Time", "Comment", "Status", "View More"])

    for date_val, dow, leave_type, hours, unit, comment, status in rows:
        ws.append([date_val, dow, leave_type, hours, unit, comment, status, "Absence Request"])

    wb.save(path)


# ---------------------------------------------------------------------------
# Synthetic test data — no real employee information
# ---------------------------------------------------------------------------

_TEST_USER = "Alex Sample"

_TEST_ROWS = [
    # Full day, no comment (Hours unit)
    (datetime(2025, 3, 3), "Monday", "Paid Time Off", 8.0, "Hours", None, "Approved"),
    # Full day, with a comment but no AM/PM keyword (Hours unit)
    (datetime(2025, 3, 10), "Monday", "Paid Time Off", 8.0, "Hours", "Team offsite week", "Approved"),
    # Half day — morning keyword
    (datetime(2025, 3, 17), "Monday", "Paid Time Off", 4.0, "Hours", "Morning appointment", "Approved"),
    # Half day — PM keyword
    (datetime(2025, 3, 24), "Monday", "Paid Time Off", 4.0, "Hours", "PM Leave", "Approved"),
    # Half day — no AM/PM indicator (should warn and default to morning)
    (datetime(2025, 3, 31), "Monday", "Paid Time Off", 4.0, "Hours", "Dentist", "Approved"),
    # Full day entered as 1 Day unit — should normalise to 8 hours
    (datetime(2025, 4, 7), "Monday", "Paid Time Off", 1.0, "Days", None, "Approved"),
]


@pytest.fixture(scope="session")
def sample_xlsx(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return path to a synthetic Workday absence XLSX with no real employee data."""
    out = tmp_path_factory.mktemp("fixtures") / "sample.xlsx"
    write_absence_xlsx(out, _TEST_USER, _TEST_ROWS)
    return out


@pytest.fixture
def make_xlsx(tmp_path: Path):
    """Factory fixture: returns a callable that writes a minimal absence XLSX."""
    def _factory(user_name: str, rows: list[tuple]) -> Path:
        out = tmp_path / "test.xlsx"
        write_absence_xlsx(out, user_name, rows)
        return out
    return _factory
