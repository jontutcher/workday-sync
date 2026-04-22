# Architecture: workday-sync

## Overview

`workday-sync` converts a Workday absence report (XLSX) into a Google Calendar-compatible ICS file.

```
test_pto.xlsx  ──►  parser  ──►  [AbsenceRequest]  ──►  ics_builder  ──►  output.ics
                                                                ▲
                                                           CLI flags
                                                     (--timezone, --out-of-office)
```

---

## Module Breakdown

### `workday_sync/models.py`

Data classes representing parsed absence data.

```python
@dataclass
class AbsenceRequest:
    date: date
    hours: float
    leave_type: str
    comment: str | None
    status: str
    user_name: str

class HalfDayPeriod(Enum):
    MORNING = "morning"    # 08:00–12:00
    AFTERNOON = "afternoon"  # 13:00–18:00
    UNKNOWN = "unknown"    # no comment indicator — defaults to morning with warning
```

### `workday_sync/parser.py`

Reads the XLSX and returns a list of `AbsenceRequest` objects.

**XLSX layout** (observed from `test_pto.xlsx`):
- Row 1: `My Absence: <User Name>` — user name extracted here
- Row 2–4: Organisation metadata (skipped)
- Row 5: Column headers
- Row 6+: Data rows until first empty row

**Column mapping** (by header, not position):

| Header        | Field        |
|---------------|--------------|
| Date          | `date`       |
| Requested     | `hours`      |
| Type          | `leave_type` |
| Comment       | `comment`    |
| Status        | `status`     |

### `workday_sync/ics_builder.py`

Converts a list of `AbsenceRequest` objects into an ICS string.

**Event timing rules:**

| Hours | Event type    | Start | End   |
|-------|---------------|-------|-------|
| == 8  | Full day      | 08:00 | 18:00 |
| < 8, comment contains morning/AM | Half day morning | 08:00 | 12:00 |
| < 8, comment contains afternoon/PM | Half day afternoon | 13:00 | 18:00 |
| < 8, no indicator | Default morning + log warning | 08:00 | 12:00 |

**Event title:** `<User Name> - PTO`

**Standard event properties:**
- `SUMMARY`: `<User Name> - PTO`
- `DTSTART` / `DTEND`: timezone-aware datetimes
- `TRANSP`: `OPAQUE` (marks as busy)
- `STATUS`: `CONFIRMED`

**Out of Office mode** (enabled via `--out-of-office`):
- Adds `X-MICROSOFT-CDO-BUSYSTATUS:OOF` — recognised by Outlook/Exchange calendar clients.

> **Google Calendar limitation:** Google Calendar's ICS import converts *all* imported events
> to `eventType: default`, silently dropping any OOF designation. The only way to create a
> native Google "Out of Office" event is via the Google Calendar API (`eventType: outOfOffice`).
> The `--out-of-office` flag is therefore most useful when sharing the ICS with Outlook/Exchange
> users, or as future groundwork for a Google Calendar API integration.

### `workday_sync/cli.py`

Click-based CLI entry point.

```
workday-sync convert <INPUT_XLSX> [OPTIONS]

Options:
  --output PATH         Output ICS file path [default: stdout]
  --timezone TEXT       Timezone for events (e.g. Europe/London) [default: Europe/London]
  --out-of-office       Add X-MICROSOFT-CDO-BUSYSTATUS:OOF (Outlook/Exchange only)
  --help                Show this message and exit.
```

---

## Data Flow

1. CLI receives `INPUT_XLSX` path and options
2. `parser.parse_xlsx(path)` → `list[AbsenceRequest]`
3. `ics_builder.build_ics(requests, timezone, out_of_office)` → ICS string
4. Output written to file or stdout

---

## Implementation Plan

| Step | Task                          | File(s)                        |
|------|-------------------------------|--------------------------------|
| 1    | Data models                   | `models.py`                    |
| 2    | XLSX parser                   | `parser.py`                    |
| 3    | ICS builder (standard events) | `ics_builder.py`               |
| 4    | CLI wiring                    | `cli.py`                       |
| 5    | Out of Office extensions      | `ics_builder.py`, `cli.py`     |

Each step follows TDD: tests written first, then implementation.

---

## Dependencies

| Package      | Purpose                            |
|--------------|------------------------------------|
| `openpyxl`   | Read `.xlsx` files                 |
| `icalendar`  | Build ICS/iCalendar data           |
| `click`      | CLI framework                      |
| `pytz`       | Timezone-aware datetime handling   |
| `pytest`     | Test framework                     |
| `freezegun`  | Freeze time in tests               |
