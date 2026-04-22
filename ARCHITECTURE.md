# Architecture: workday-sync

## Overview

`workday-sync` converts a Workday absence report (XLSX) into calendar events. It supports two output modes:

- **ICS file** — importable into any calendar client (default: stdout)
- **Google Calendar API** — pushes events directly as native Out of Office events (`--gcal`)

```
absences.xlsx  ──►  parser  ──►  [AbsenceRequest]  ──►  ics_builder  ──►  output.ics / stdout
                                        │
                                        └──────────────►  gcal_client  ──►  Google Calendar API
                                                              ▲
                                                         CLI flags
                                              (--gcal, --calendar-id, --client-secrets,
                                               --timezone, --out-of-office, --output)
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

    def time_window(self) -> tuple[time, time]:
        ...  # returns (start_time, end_time) based on hours and comment

    @property
    def event_title(self) -> str:
        return f"{self.user_name} - {self.leave_type}"

class HalfDayPeriod(Enum):
    MORNING = "morning"      # 08:00–12:00
    AFTERNOON = "afternoon"  # 13:00–18:00
    UNKNOWN = "unknown"      # no comment indicator — defaults to morning with warning
```

`AbsenceRequest.time_window()` is the single source of truth for start/end time logic. Both `ics_builder` and `gcal_client` call it — no duplication.

### `workday_sync/parser.py`

Reads the XLSX and returns a `ParseResult(requests, warnings)` named tuple.

**XLSX layout** (observed from Workday exports):
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

Warnings (e.g. ambiguous half-day periods) are collected in `ParseResult.warnings` as strings and surfaced by the CLI on stderr — Python's `warnings` module is not used.

### `workday_sync/ics_builder.py`

Converts a list of `AbsenceRequest` objects into an ICS string.

**Event timing rules** (via `AbsenceRequest.time_window()`):

| Hours | Event type    | Start | End   |
|-------|---------------|-------|-------|
| == 8  | Full day      | 08:00 | 18:00 |
| < 8, comment contains morning/AM | Half day morning | 08:00 | 12:00 |
| < 8, comment contains afternoon/PM | Half day afternoon | 13:00 | 18:00 |
| < 8, no indicator | Default morning + warning | 08:00 | 12:00 |

**Standard event properties:**
- `SUMMARY`: `<User Name> - <Leave Type>`
- `DTSTART` / `DTEND`: timezone-aware datetimes
- `TRANSP`: `OPAQUE` (marks as busy)
- `STATUS`: `CONFIRMED`

**Out of Office mode** (`--out-of-office`):
- Adds `X-MICROSOFT-CDO-BUSYSTATUS:OOF` — recognised by Outlook/Exchange.
- Has no effect on the `--gcal` path (Google Calendar API events are always native OOF).

> **Google Calendar ICS limitation:** ICS import converts all events to `eventType: default`,
> silently dropping any OOF designation. Use `--gcal` for native Google "Out of Office" events.

### `workday_sync/gcal_client.py`

Pushes absences to Google Calendar as native `eventType: outOfOffice` events.

```python
def get_credentials(client_secrets_path, token_path) -> Credentials
    # Raises FileNotFoundError (with setup instructions) if secrets missing
    # Returns cached token if valid; silently refreshes if expired
    # Falls back to InstalledAppFlow browser flow (port=0)
    # Persists token to ~/.config/workday-sync/token.json (chmod 0600)

def build_service(credentials) -> Resource
    # Returns googleapiclient Resource for Calendar v3 API

def build_event_body(req: AbsenceRequest, timezone: str) -> dict
    # Constructs OOF event body using req.time_window() for start/end

def push_events(requests, service, calendar_id, timezone) -> list[dict]
    # Calls events().insert() for each request; propagates HttpError
```

**Event body structure:**
```json
{
  "summary": "<User Name> - <Leave Type>",
  "eventType": "outOfOffice",
  "start": { "dateTime": "YYYY-MM-DDTHH:MM:SS", "timeZone": "<tz>" },
  "end":   { "dateTime": "YYYY-MM-DDTHH:MM:SS", "timeZone": "<tz>" },
  "outOfOfficeProperties": {
    "autoDeclineMode": "declineOnlyNewConflictingInvitations",
    "declineMessage": "I am out of office and will respond when I return."
  },
  "status": "confirmed",
  "transparency": "opaque"
}
```

**Token caching:** `~/.config/workday-sync/token.json` (created on first run, chmod 0600).
First-time use opens a browser for OAuth consent; subsequent runs use the cached token.

### `workday_sync/cli.py`

Click-based CLI entry point.

```
workday-sync convert <INPUT_XLSX> [OPTIONS]

Options:
  --output PATH           Output ICS file path [default: stdout]
  --timezone TEXT         IANA timezone name [default: Europe/London]
  --out-of-office         Add X-MICROSOFT-CDO-BUSYSTATUS:OOF (Outlook/Exchange only)
  --gcal                  Push to Google Calendar as native Out of Office events
  --calendar-id TEXT      Google Calendar ID [default: primary]
  --client-secrets PATH   Path to OAuth client_secret.json [default: ~/.config/workday-sync/client_secret.json]
  --help                  Show this message and exit.
```

**Output mode logic:**

| Flags | ICS output | GCal push |
|-------|------------|-----------|
| *(none)* | stdout | no |
| `--output` | file | no |
| `--gcal` | no | yes |
| `--gcal --output` | file | yes |

---

## Google Calendar OAuth Setup

To use `--gcal`, you need a Google Cloud OAuth 2.0 Desktop app credential. One-time setup:

### 1. Create or select a Google Cloud project

```bash
gcloud config set project YOUR_PROJECT_ID
```

Or create a new one:
```bash
gcloud projects create my-workday-sync --name="workday-sync"
gcloud config set project my-workday-sync
```

### 2. Enable the Google Calendar API

```bash
gcloud services enable calendar-json.googleapis.com
```

### 3. Configure the OAuth consent screen

Go to: `https://console.cloud.google.com/apis/credentials/consent`

- User type: **External** (or **Internal** for Google Workspace orgs)
- App name: `workday-sync`
- Support email + developer contact: your email
- Skip scopes and test users — save and continue through to the end

### 4. Create a Desktop app OAuth credential

Go to: `https://console.cloud.google.com/apis/credentials`

- Click **+ Create Credentials → OAuth client ID**
- Application type: **Desktop app**
- Name: `workday-sync`
- Click **Create**, then **Download JSON**

### 5. Install the credential

```bash
mkdir -p ~/.config/workday-sync
mv ~/Downloads/client_secret_*.json ~/.config/workday-sync/client_secret.json
chmod 600 ~/.config/workday-sync/client_secret.json
```

Use `--client-secrets /path/to/file.json` to override the default location.

### First run

```bash
workday-sync convert absences.xlsx --gcal
```

A browser window will open for Google OAuth consent. After granting access, the token is cached at `~/.config/workday-sync/token.json` and the browser flow won't repeat unless the token is revoked or deleted.

> **Note:** The consent screen may show an "unverified app" warning if the app hasn't been
> submitted for Google verification. Click **Advanced → Go to workday-sync (unsafe)** to proceed
> for personal use.

---

## Data Flow

### ICS path

1. CLI receives `INPUT_XLSX` path and options
2. `parser.parse_xlsx(path)` → `ParseResult(requests, warnings)`
3. Warnings emitted to stderr
4. `ics_builder.build_ics(requests, timezone, out_of_office)` → ICS string
5. Output written to file or stdout

### GCal path

1. CLI receives `INPUT_XLSX` path and `--gcal` flag
2. `parser.parse_xlsx(path)` → `ParseResult(requests, warnings)`
3. Warnings emitted to stderr
4. `gcal_client.get_credentials(secrets_path)` → OAuth credentials (browser if first run)
5. `gcal_client.build_service(creds)` → Calendar API resource
6. `gcal_client.push_events(requests, service, calendar_id, timezone)` → created events
7. Event count reported to stderr

Both paths can run together with `--gcal --output`.

---

## Dependencies

| Package                        | Purpose                                       |
|--------------------------------|-----------------------------------------------|
| `openpyxl`                     | Read `.xlsx` files                            |
| `icalendar`                    | Build ICS/iCalendar data                      |
| `click`                        | CLI framework                                 |
| `pytz`                         | Timezone-aware datetime handling              |
| `google-api-python-client`     | Google Calendar API client                    |
| `google-auth`                  | Google OAuth credentials                      |
| `google-auth-oauthlib`         | OAuth 2.0 installed-app browser flow          |
| `pytest`                       | Test framework                                |
| `pytest-mock`                  | Mock/patch support in tests                   |
| `freezegun`                    | Freeze time in tests                          |
