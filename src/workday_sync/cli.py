"""Command-line interface for workday-sync."""

from __future__ import annotations

from pathlib import Path

import click
import pytz

from workday_sync.ics_builder import build_ics
from workday_sync.parser import parse_xlsx


@click.group()
def cli() -> None:
    """workday-sync: Convert a Workday absence export to a Google Calendar ICS file."""


@cli.command()
@click.argument("input_xlsx", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="Output ICS file path. Defaults to stdout.",
)
@click.option(
    "--timezone",
    "-t",
    default="Europe/London",
    show_default=True,
    help="IANA timezone name for event datetimes (e.g. Europe/London, America/New_York).",
)
@click.option(
    "--out-of-office",
    is_flag=True,
    default=False,
    help=(
        "Add X-MICROSOFT-CDO-BUSYSTATUS:OOF to each event. "
        "Recognised by Outlook/Exchange; Google Calendar cannot import OOF event types "
        "via ICS and will treat these as regular busy events regardless."
    ),
)
def convert(
    input_xlsx: Path,
    output: Path | None,
    timezone: str,
    out_of_office: bool,
) -> None:
    """Convert INPUT_XLSX (a Workday absence export) to an ICS file.

    INPUT_XLSX is the path to the .xlsx file downloaded from the Workday
    'My Absence' page.

    By default the ICS content is written to stdout. Use --output to write
    to a file instead.

    \b
    Examples:
      workday-sync convert absences.xlsx
      workday-sync convert absences.xlsx --output calendar.ics
      workday-sync convert absences.xlsx --timezone America/New_York --out-of-office
    """
    # Validate timezone before doing any work
    try:
        pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        raise click.BadParameter(
            f"{timezone!r} is not a valid IANA timezone. "
            "See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
            param_hint="--timezone",
        )

    requests = parse_xlsx(input_xlsx)
    ics_content = build_ics(requests, timezone=timezone, out_of_office=out_of_office)

    if output is None:
        click.echo(ics_content, nl=False)
    else:
        output.write_text(ics_content, encoding="utf-8")
        click.echo(f"Written to {output}", err=True)
