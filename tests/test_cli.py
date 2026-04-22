"""Tests for workday_sync.cli."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from workday_sync.cli import cli

FIXTURE = Path(__file__).parent / "fixtures" / "test_pto.xlsx"


class TestConvertCommand:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--timezone" in result.output
        assert "--out-of-office" in result.output

    def test_convert_writes_ics_to_stdout(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(FIXTURE)])
        assert result.exit_code == 0
        assert "BEGIN:VCALENDAR" in result.output
        assert "BEGIN:VEVENT" in result.output
        assert "Jon Tutcher - PTO" in result.output

    def test_convert_writes_to_file(self, tmp_path: Path) -> None:
        out_file = tmp_path / "output.ics"
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(FIXTURE), "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "BEGIN:VCALENDAR" in content

    def test_custom_timezone(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["convert", str(FIXTURE), "--timezone", "America/New_York"]
        )
        assert result.exit_code == 0
        assert "BEGIN:VCALENDAR" in result.output

    def test_invalid_timezone_shows_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(FIXTURE), "--timezone", "Mars/Olympus"])
        assert result.exit_code != 0
        assert "timezone" in result.output.lower() or "error" in result.output.lower()

    def test_missing_file_shows_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", "nonexistent.xlsx"])
        assert result.exit_code != 0

    def test_out_of_office_flag_adds_oof_property(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(FIXTURE), "--out-of-office"])
        assert result.exit_code == 0
        assert "OOF" in result.output

    def test_default_timezone_is_london(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["convert", str(FIXTURE)])
        assert result.exit_code == 0
        # London timezone abbreviation should appear in the ICS
        assert "Europe/London" in result.output or "GMT" in result.output or "BST" in result.output
