"""Google Calendar API client for workday-sync.

Handles OAuth authentication and creation of Out of Office events
via the Google Calendar API (eventType: outOfOffice).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build as discovery_build
from googleapiclient.errors import HttpError

from workday_sync.models import AbsenceRequest

# OAuth scope — events only, not full calendar access
SCOPES: list[str] = ["https://www.googleapis.com/auth/calendar.events"]

_DEFAULT_CONFIG_DIR = Path.home() / ".config" / "workday-sync"
_DEFAULT_TOKEN_PATH = _DEFAULT_CONFIG_DIR / "token.json"
_DEFAULT_SECRETS_PATH = _DEFAULT_CONFIG_DIR / "client_secret.json"

_OOF_DECLINE_MESSAGE = "I am out of office and will respond when I return."

_log = logging.getLogger(__name__)


def get_credentials(
    client_secrets_path: Path = _DEFAULT_SECRETS_PATH,
    token_path: Path = _DEFAULT_TOKEN_PATH,
) -> Credentials:
    """Return valid OAuth credentials, running the browser flow if needed.

    1. Raises FileNotFoundError if client_secrets_path does not exist.
    2. Returns cached token immediately if it is still valid.
    3. Silently refreshes an expired token when a refresh token is available.
       If the refresh token has been revoked, deletes the cached token and
       falls through to the browser flow.
    4. Runs InstalledAppFlow (opens browser, listens on an ephemeral port).
    5. Persists the resulting credentials to token_path (chmod 0600).

    Args:
        client_secrets_path: Path to client_secret.json from Google Cloud Console.
        token_path: Path where the cached OAuth token is stored.

    Raises:
        FileNotFoundError: If client_secrets_path does not exist.
    """
    if not client_secrets_path.exists():
        raise FileNotFoundError(
            f"client_secret.json not found at {client_secrets_path}.\n\n"
            "To set up Google Calendar access:\n"
            "  1. Go to https://console.cloud.google.com/\n"
            "  2. Create a project and enable the Google Calendar API.\n"
            "  3. Create an OAuth 2.0 credential (Desktop app type).\n"
            "  4. Download client_secret.json and save it to:\n"
            f"       {client_secrets_path}\n"
            "  5. Re-run this command.\n\n"
            "Or use --client-secrets to specify a different path."
        )

    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            # Refresh token revoked — delete stale cache and re-authenticate
            token_path.unlink(missing_ok=True)
            creds = None

    if creds is None or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), SCOPES)
        creds = flow.run_local_server(port=0)

    _save_token(creds, token_path)
    return creds


def build_service(credentials: Credentials) -> Any:
    """Return a Google Calendar API service resource.

    Extracted as a separate function so tests can inject a fake service.

    Args:
        credentials: Valid OAuth credentials.

    Returns:
        A googleapiclient Resource for the Calendar v3 API.
    """
    return discovery_build("calendar", "v3", credentials=credentials)


def build_event_body(req: AbsenceRequest, timezone: str) -> dict[str, Any]:
    """Construct a Google Calendar API event body for an OOF event.

    Args:
        req: The absence to represent as a calendar event.
        timezone: IANA timezone name (e.g. 'Europe/London').

    Returns:
        A dict ready to be passed to ``service.events().insert(body=...)``.
    """
    start_time, end_time = req.time_window()

    start_dt = datetime.combine(req.date, start_time)
    end_dt = datetime.combine(req.date, end_time)

    return {
        "id": req.unique_key,
        "summary": req.event_title,
        "eventType": "outOfOffice",
        "start": {
            "dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": timezone,
        },
        "outOfOfficeProperties": {
            "autoDeclineMode": "declineOnlyNewConflictingInvitations",
            "declineMessage": _OOF_DECLINE_MESSAGE,
        },
        "status": "confirmed",
        "transparency": "opaque",
    }


def push_events(
    requests: list[AbsenceRequest],
    service: Any,
    calendar_id: str = "primary",
    timezone: str = "Europe/London",
) -> list[dict[str, Any]]:
    """Create one Google Calendar OOF event per AbsenceRequest.

    Args:
        requests: Parsed absence records to push.
        service: A Google Calendar API service resource (from :func:`build_service`).
        calendar_id: Calendar to create events in ('primary' or a full calendar ID).
        timezone: IANA timezone name for event datetimes.

    Returns:
        List of created event resource dicts returned by the API.

    Raises:
        googleapiclient.errors.HttpError: Propagated on API errors (e.g. 429, 403).
            A 409 (already exists) response is treated as success and silently
            skipped — the event is omitted from the returned list.
    """
    created: list[dict[str, Any]] = []
    for req in requests:
        body = build_event_body(req, timezone)
        try:
            event = service.events().insert(calendarId=calendar_id, body=body).execute()
            created.append(event)
        except HttpError as exc:
            if exc.resp.status == 409:
                _log.info("Event %s already exists; skipping.", req.unique_key)
            else:
                raise
    return created


# ── Private helpers ───────────────────────────────────────────────────────────

def _save_token(creds: Credentials, token_path: Path) -> None:
    """Persist credentials to token_path and restrict file permissions to 0600."""
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    token_path.chmod(0o600)
