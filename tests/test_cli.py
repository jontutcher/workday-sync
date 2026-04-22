"""Tests for workday_sync.cli."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from workday_sync.cli import cli


class TestConvertCommand:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--timezone" in result.output
        assert "--out-of-office" in result.output

    def test_convert_writes_ics_to_stdout(self, sample_xlsx: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(sample_xlsx)])
        assert result.exit_code == 0
        assert "BEGIN:VCALENDAR" in result.stdout
        assert "BEGIN:VEVENT" in result.stdout
        assert "Alex Sample - Paid Time Off" in result.stdout

    def test_convert_writes_to_file(self, sample_xlsx: Path, tmp_path: Path) -> None:
        out_file = tmp_path / "output.ics"
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(sample_xlsx), "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "BEGIN:VCALENDAR" in content

    def test_custom_timezone(self, sample_xlsx: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["convert", str(sample_xlsx), "--timezone", "America/New_York"]
        )
        assert result.exit_code == 0
        assert "BEGIN:VCALENDAR" in result.stdout

    def test_invalid_timezone_shows_error(self, sample_xlsx: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(sample_xlsx), "--timezone", "Mars/Olympus"])
        assert result.exit_code != 0
        assert "timezone" in result.output.lower() or "error" in result.output.lower()

    def test_missing_file_shows_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "nonexistent.xlsx"])
        assert result.exit_code != 0

    def test_out_of_office_flag_adds_oof_property(self, sample_xlsx: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(sample_xlsx), "--out-of-office"])
        assert result.exit_code == 0
        assert "OOF" in result.stdout

    def test_default_timezone_is_london(self, sample_xlsx: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(sample_xlsx)])
        assert result.exit_code == 0
        assert "Europe/London" in result.stdout or "GMT" in result.stdout or "BST" in result.stdout

    def test_ambiguous_half_day_warning_on_stderr(self, sample_xlsx: Path) -> None:
        """Ambiguous half-day warnings must appear on stderr, not mixed into ICS stdout."""
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(sample_xlsx)])
        assert result.exit_code == 0
        # Warning appears on stderr
        assert "Warning:" in result.stderr
        assert "2025-03-31" in result.stderr
        # ICS stdout is clean of warning text
        assert "Warning:" not in result.stdout


class TestConvertCommandGcal:
    def test_gcal_flag_in_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "--help"])
        assert result.exit_code == 0
        assert "--gcal" in result.output

    def test_calendar_id_flag_in_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "--help"])
        assert "--calendar-id" in result.output

    def test_client_secrets_flag_in_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "--help"])
        assert "--client-secrets" in result.output

    def test_gcal_alone_does_not_write_ics_to_stdout(
        self, sample_xlsx: Path, mocker
    ) -> None:
        mocker.patch("workday_sync.gcal_client.get_credentials")
        mocker.patch("workday_sync.gcal_client.build_service")
        mocker.patch(
            "workday_sync.gcal_client.push_events",
            return_value=[{"id": "x"}] * 6,
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(sample_xlsx), "--gcal"])
        assert result.exit_code == 0
        assert "BEGIN:VCALENDAR" not in result.stdout

    def test_gcal_with_output_writes_ics_file(
        self, sample_xlsx: Path, tmp_path: Path, mocker
    ) -> None:
        mocker.patch("workday_sync.gcal_client.get_credentials")
        mocker.patch("workday_sync.gcal_client.build_service")
        mocker.patch(
            "workday_sync.gcal_client.push_events",
            return_value=[{"id": "x"}],
        )
        out_file = tmp_path / "out.ics"
        runner = CliRunner()
        result = runner.invoke(
            cli, ["convert", str(sample_xlsx), "--gcal", "--output", str(out_file)]
        )
        assert result.exit_code == 0
        assert out_file.exists()
        assert "BEGIN:VCALENDAR" in out_file.read_text()

    def test_gcal_reports_event_count_on_stderr(
        self, sample_xlsx: Path, mocker
    ) -> None:
        mocker.patch("workday_sync.gcal_client.get_credentials")
        mocker.patch("workday_sync.gcal_client.build_service")
        mocker.patch(
            "workday_sync.gcal_client.push_events",
            return_value=[{"id": str(i)} for i in range(6)],
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(sample_xlsx), "--gcal"])
        assert result.exit_code == 0
        assert "6" in result.stderr

    def test_gcal_passes_calendar_id(self, sample_xlsx: Path, mocker) -> None:
        mocker.patch("workday_sync.gcal_client.get_credentials")
        mocker.patch("workday_sync.gcal_client.build_service")
        mock_push = mocker.patch(
            "workday_sync.gcal_client.push_events", return_value=[]
        )
        runner = CliRunner()
        runner.invoke(
            cli,
            ["convert", str(sample_xlsx), "--gcal", "--calendar-id", "team@example.com"],
        )
        call_kwargs = mock_push.call_args.kwargs
        assert call_kwargs["calendar_id"] == "team@example.com"

    def test_gcal_passes_timezone(self, sample_xlsx: Path, mocker) -> None:
        mocker.patch("workday_sync.gcal_client.get_credentials")
        mocker.patch("workday_sync.gcal_client.build_service")
        mock_push = mocker.patch(
            "workday_sync.gcal_client.push_events", return_value=[]
        )
        runner = CliRunner()
        runner.invoke(
            cli,
            ["convert", str(sample_xlsx), "--gcal", "--timezone", "America/New_York"],
        )
        call_kwargs = mock_push.call_args.kwargs
        assert call_kwargs["timezone"] == "America/New_York"

    def test_missing_client_secrets_shows_helpful_error(
        self, sample_xlsx: Path, tmp_path: Path, mocker
    ) -> None:
        mocker.patch(
            "workday_sync.gcal_client.get_credentials",
            side_effect=FileNotFoundError("client_secret.json not found at /fake/path"),
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["convert", str(sample_xlsx), "--gcal",
             "--client-secrets", str(tmp_path / "fake.json")],
        )
        assert result.exit_code != 0
        assert "client_secret" in result.output.lower() or "error" in result.output.lower()

    def test_out_of_office_with_gcal_but_no_output_warns(
        self, sample_xlsx: Path, mocker
    ) -> None:
        """--out-of-office has no effect on the GCal path; user should be informed."""
        mocker.patch("workday_sync.gcal_client.get_credentials")
        mocker.patch("workday_sync.gcal_client.build_service")
        mocker.patch("workday_sync.gcal_client.push_events", return_value=[])
        runner = CliRunner()
        result = runner.invoke(
            cli, ["convert", str(sample_xlsx), "--gcal", "--out-of-office"]
        )
        assert result.exit_code == 0
        assert "no effect" in result.stderr.lower() or "out-of-office" in result.stderr.lower()
