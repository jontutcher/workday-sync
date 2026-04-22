"""Data models for workday-sync."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
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
        return f"{self.user_name} - PTO"
