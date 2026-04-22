"""Data models for workday-sync."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, time
from enum import Enum


class HalfDayPeriod(Enum):
    """Which half of the day a partial absence covers."""

    MORNING = "morning"
    AFTERNOON = "afternoon"
    UNKNOWN = "unknown"

    @classmethod
    def from_comment(cls, comment: str | None) -> HalfDayPeriod:
        """Infer morning/afternoon from a free-text comment string."""
        if not comment:
            return cls.UNKNOWN
        lower = comment.lower()
        if re.search(r"\bmorning\b|\bam\b", lower):
            return cls.MORNING
        if re.search(r"\bafternoon\b|\bpm\b", lower):
            return cls.AFTERNOON
        return cls.UNKNOWN


@dataclass
class AbsenceRequest:
    """A single day (or partial day) of absence from Workday."""

    date: date
    hours: float
    leave_type: str
    comment: str | None
    status: str
    user_name: str

    @property
    def is_full_day(self) -> bool:
        return self.hours >= 8.0

    @property
    def is_half_day(self) -> bool:
        return not self.is_full_day

    @property
    def event_title(self) -> str:
        return f"{self.user_name} - {self.leave_type}"

    def time_window(self) -> tuple[time, time]:
        """Return the (start, end) local times for this absence event.

        Full day  → 08:00–18:00
        Morning   → 08:00–12:00  (comment contains morning/AM keyword)
        Afternoon → 13:00–18:00  (comment contains afternoon/PM keyword)
        Unknown   → 08:00–12:00  (default when comment gives no hint)
        """
        if self.is_full_day:
            return time(8, 0), time(18, 0)
        period = HalfDayPeriod.from_comment(self.comment)
        if period is HalfDayPeriod.AFTERNOON:
            return time(13, 0), time(18, 0)
        return time(8, 0), time(12, 0)
