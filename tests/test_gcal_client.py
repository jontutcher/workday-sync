"""Tests for workday_sync.gcal_client."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from googleapiclient.errors import HttpError

from workday_sync.gcal_client import (
    _DEFAULT_SECRETS_PATH,
    _DEFAULT_TOKEN_PATH,
    build_event_body,
    build_service,
    get_credentials,
    push_events,
)
from workday_sync.models import AbsenceRequest


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_request(**kwargs) -> AbsenceRequest:
    defaults = dict(
        date=date(2025, 3, 3),
        hours=8.0,
        leave_type="Paid Time Off",
        comment=None,
        status="Approved",
        user_name="Alex Sample",
    )
    defaults.update(kwargs)
    return AbsenceRequest(**defaults)


def _write_fake_secrets(path: Path) -> None:
    """Write a minimal client_secret.json structure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "installed": {
            "client_id": "fake-client-id.apps.googleusercontent.com",
            "client_secret": "fake-secret",
            "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }), encoding="utf-8")


def _write_fake_token(path: Path) -> None:
    """Write a minimal token.json structure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "token": "fake-access-token",
        "refresh_token": "fake-refresh-token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "fake-client-id",
        "client_secret": "fake-secret",
        "scopes": ["https://www.googleapis.com/auth/calendar.events"],
    }), encoding="utf-8")


# ── build_event_body ──────────────────────────────────────────────────────────

class TestBuildEventBody:
    def test_event_type_is_out_of_office(self) -> None:
        body = build_event_body(make_request(), timezone="Europe/London")
        assert body["eventType"] == "outOfOffice"

    def test_summary_matches_event_title(self) -> None:
        body = build_event_body(make_request(), timezone="Europe/London")
        assert body["summary"] == "Alex Sample - Paid Time Off"

    def test_full_day_start_is_0800(self) -> None:
        body = build_event_body(make_request(hours=8.0), timezone="Europe/London")
        assert body["start"]["dateTime"].endswith("T08:00:00")

    def test_full_day_end_is_1800(self) -> None:
        body = build_event_body(make_request(hours=8.0), timezone="Europe/London")
        assert body["end"]["dateTime"].endswith("T18:00:00")

    def test_morning_half_day_start_and_end(self) -> None:
        body = build_event_body(
            make_request(hours=4.0, comment="Morning appointment"), timezone="Europe/London"
        )
        assert body["start"]["dateTime"].endswith("T08:00:00")
        assert body["end"]["dateTime"].endswith("T12:00:00")

    def test_afternoon_half_day_start_and_end(self) -> None:
        body = build_event_body(
            make_request(hours=4.0, comment="PM Leave"), timezone="Europe/London"
        )
        assert body["start"]["dateTime"].endswith("T13:00:00")
        assert body["end"]["dateTime"].endswith("T18:00:00")

    def test_unknown_half_day_defaults_to_morning(self) -> None:
        body = build_event_body(
            make_request(hours=4.0, comment="Dentist"), timezone="Europe/London"
        )
        assert body["start"]["dateTime"].endswith("T08:00:00")
        assert body["end"]["dateTime"].endswith("T12:00:00")

    def test_timezone_applied(self) -> None:
        body = build_event_body(make_request(), timezone="America/New_York")
        assert body["start"]["timeZone"] == "America/New_York"
        assert body["end"]["timeZone"] == "America/New_York"

    def test_out_of_office_properties_present(self) -> None:
        body = build_event_body(make_request(), timezone="Europe/London")
        assert "outOfOfficeProperties" in body
        assert "autoDeclineMode" in body["outOfOfficeProperties"]
        assert "declineMessage" in body["outOfOfficeProperties"]

    def test_status_is_confirmed(self) -> None:
        body = build_event_body(make_request(), timezone="Europe/London")
        assert body["status"] == "confirmed"

    def test_transparency_is_opaque(self) -> None:
        body = build_event_body(make_request(), timezone="Europe/London")
        assert body["transparency"] == "opaque"

    def test_date_in_start_datetime(self) -> None:
        body = build_event_body(make_request(date=date(2025, 3, 3)), timezone="Europe/London")
        assert body["start"]["dateTime"].startswith("2025-03-03")

    def test_id_matches_unique_key(self) -> None:
        req = make_request()
        body = build_event_body(req, timezone="Europe/London")
        assert body["id"] == req.unique_key


# ── get_credentials ───────────────────────────────────────────────────────────

class TestGetCredentials:
    def test_raises_if_secrets_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="client_secret"):
            get_credentials(
                client_secrets_path=tmp_path / "missing.json",
                token_path=tmp_path / "token.json",
            )

    def test_returns_cached_valid_token(self, tmp_path: Path, mocker) -> None:
        secrets = tmp_path / "client_secret.json"
        token = tmp_path / "token.json"
        _write_fake_secrets(secrets)
        _write_fake_token(token)

        fake_creds = mocker.MagicMock()
        fake_creds.valid = True
        mocker.patch(
            "workday_sync.gcal_client.Credentials.from_authorized_user_file",
            return_value=fake_creds,
        )

        result = get_credentials(client_secrets_path=secrets, token_path=token)
        assert result is fake_creds

    def test_refreshes_expired_token_silently(self, tmp_path: Path, mocker) -> None:
        secrets = tmp_path / "client_secret.json"
        token = tmp_path / "token.json"
        _write_fake_secrets(secrets)
        _write_fake_token(token)

        fake_creds = mocker.MagicMock()
        fake_creds.valid = False
        fake_creds.expired = True
        fake_creds.refresh_token = "some-refresh-token"
        fake_creds.to_json.return_value = '{"token": "refreshed"}'

        # After refresh is called, mark credentials as valid so the code
        # doesn't fall through to the browser flow.
        def _mark_valid(_request: object) -> None:
            fake_creds.valid = True

        fake_creds.refresh.side_effect = _mark_valid

        mocker.patch(
            "workday_sync.gcal_client.Credentials.from_authorized_user_file",
            return_value=fake_creds,
        )
        mock_request = mocker.patch("workday_sync.gcal_client.Request")

        get_credentials(client_secrets_path=secrets, token_path=token)

        fake_creds.refresh.assert_called_once_with(mock_request())

    def test_runs_browser_flow_when_no_token(self, tmp_path: Path, mocker) -> None:
        secrets = tmp_path / "client_secret.json"
        token = tmp_path / "token.json"
        _write_fake_secrets(secrets)
        # No token.json — should trigger browser flow

        fake_creds = mocker.MagicMock()
        fake_creds.valid = True
        fake_creds.to_json.return_value = '{"token": "new"}'

        mock_flow = mocker.MagicMock()
        mock_flow.run_local_server.return_value = fake_creds
        mocker.patch(
            "workday_sync.gcal_client.InstalledAppFlow.from_client_secrets_file",
            return_value=mock_flow,
        )

        get_credentials(client_secrets_path=secrets, token_path=token)

        mock_flow.run_local_server.assert_called_once_with(port=0)

    def test_saves_token_after_browser_flow(self, tmp_path: Path, mocker) -> None:
        secrets = tmp_path / "client_secret.json"
        token = tmp_path / "token.json"
        _write_fake_secrets(secrets)

        fake_creds = mocker.MagicMock()
        fake_creds.valid = True
        fake_creds.to_json.return_value = '{"token": "new"}'

        mock_flow = mocker.MagicMock()
        mock_flow.run_local_server.return_value = fake_creds
        mocker.patch(
            "workday_sync.gcal_client.InstalledAppFlow.from_client_secrets_file",
            return_value=mock_flow,
        )

        get_credentials(client_secrets_path=secrets, token_path=token)

        assert token.exists()
        assert token.read_text() == '{"token": "new"}'

    def test_token_file_is_chmod_600(self, tmp_path: Path, mocker) -> None:
        secrets = tmp_path / "client_secret.json"
        token = tmp_path / "token.json"
        _write_fake_secrets(secrets)

        fake_creds = mocker.MagicMock()
        fake_creds.valid = True
        fake_creds.to_json.return_value = '{"token": "new"}'

        mock_flow = mocker.MagicMock()
        mock_flow.run_local_server.return_value = fake_creds
        mocker.patch(
            "workday_sync.gcal_client.InstalledAppFlow.from_client_secrets_file",
            return_value=mock_flow,
        )

        get_credentials(client_secrets_path=secrets, token_path=token)

        import stat
        mode = token.stat().st_mode & 0o777
        assert mode == 0o600

    def test_deletes_stale_token_and_reruns_flow_on_refresh_error(
        self, tmp_path: Path, mocker
    ) -> None:
        from google.auth.exceptions import RefreshError

        secrets = tmp_path / "client_secret.json"
        token = tmp_path / "token.json"
        _write_fake_secrets(secrets)
        _write_fake_token(token)

        expired_creds = mocker.MagicMock()
        expired_creds.valid = False
        expired_creds.expired = True
        expired_creds.refresh_token = "bad-token"
        expired_creds.refresh.side_effect = RefreshError("revoked")
        mocker.patch(
            "workday_sync.gcal_client.Credentials.from_authorized_user_file",
            return_value=expired_creds,
        )

        new_creds = mocker.MagicMock()
        new_creds.valid = True
        new_creds.to_json.return_value = '{"token": "fresh"}'
        mock_flow = mocker.MagicMock()
        mock_flow.run_local_server.return_value = new_creds
        mocker.patch(
            "workday_sync.gcal_client.InstalledAppFlow.from_client_secrets_file",
            return_value=mock_flow,
        )

        result = get_credentials(client_secrets_path=secrets, token_path=token)

        mock_flow.run_local_server.assert_called_once()
        assert result is new_creds


# ── build_service ─────────────────────────────────────────────────────────────

class TestBuildService:
    def test_returns_service_resource(self, mocker) -> None:
        fake_creds = mocker.MagicMock()
        mock_build = mocker.patch("workday_sync.gcal_client.discovery_build")
        mock_build.return_value = mocker.MagicMock()

        result = build_service(fake_creds)

        mock_build.assert_called_once_with("calendar", "v3", credentials=fake_creds)
        assert result is mock_build.return_value


# ── push_events ───────────────────────────────────────────────────────────────

class TestPushEvents:
    def test_calls_insert_for_each_request(self, mocker) -> None:
        service = mocker.MagicMock()
        service.events.return_value.insert.return_value.execute.return_value = {"id": "x"}

        requests = [make_request(date=date(2025, 3, d)) for d in (3, 10, 17)]
        push_events(requests, service)

        assert service.events.return_value.insert.call_count == 3

    def test_passes_calendar_id(self, mocker) -> None:
        service = mocker.MagicMock()
        service.events.return_value.insert.return_value.execute.return_value = {"id": "x"}

        push_events([make_request()], service, calendar_id="team@example.com")

        call_kwargs = service.events.return_value.insert.call_args_list[0].kwargs
        assert call_kwargs["calendarId"] == "team@example.com"

    def test_returns_list_of_created_events(self, mocker) -> None:
        service = mocker.MagicMock()
        service.events.return_value.insert.return_value.execute.side_effect = [
            {"id": "a"}, {"id": "b"},
        ]

        result = push_events(
            [make_request(date=date(2025, 3, d)) for d in (3, 10)], service
        )

        assert result == [{"id": "a"}, {"id": "b"}]

    def test_empty_list_returns_empty(self, mocker) -> None:
        service = mocker.MagicMock()
        result = push_events([], service)
        assert result == []
        service.events.return_value.insert.assert_not_called()

    def _make_http_error(self, status: int) -> HttpError:
        resp = type("Response", (), {"status": status, "reason": str(status)})()
        return HttpError(resp=resp, content=b"already exists")

    def test_409_is_skipped_and_not_in_result(self, mocker) -> None:
        service = mocker.MagicMock()
        service.events.return_value.insert.return_value.execute.side_effect = (
            self._make_http_error(409)
        )

        result = push_events([make_request()], service)

        assert result == []

    def test_409_does_not_raise(self, mocker) -> None:
        service = mocker.MagicMock()
        service.events.return_value.insert.return_value.execute.side_effect = (
            self._make_http_error(409)
        )

        push_events([make_request()], service)  # must not raise

    def test_409_is_logged(self, mocker, caplog) -> None:
        import logging

        service = mocker.MagicMock()
        service.events.return_value.insert.return_value.execute.side_effect = (
            self._make_http_error(409)
        )

        with caplog.at_level(logging.INFO, logger="workday_sync.gcal_client"):
            push_events([make_request()], service)

        assert any("already exists" in r.message for r in caplog.records)

    def test_non_409_http_error_is_reraised(self, mocker) -> None:
        service = mocker.MagicMock()
        service.events.return_value.insert.return_value.execute.side_effect = (
            self._make_http_error(403)
        )

        with pytest.raises(HttpError):
            push_events([make_request()], service)

    def test_409_on_one_event_does_not_block_others(self, mocker) -> None:
        service = mocker.MagicMock()
        service.events.return_value.insert.return_value.execute.side_effect = [
            self._make_http_error(409),
            {"id": "new-event"},
        ]

        result = push_events(
            [make_request(date=date(2025, 3, 3)), make_request(date=date(2025, 3, 10))],
            service,
        )

        assert result == [{"id": "new-event"}]
